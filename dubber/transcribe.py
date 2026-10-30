"""Stage 2 — speech (any language, even several in one video) to timed text with faster-whisper.

Whisper transcribes in ONE language per 30-s window and silently drops speech in another language: forcing English
lost a whole French passage, and auto-detection lost the English intro before it (measured 2026-10-16). So the
language is detected for each stretch of speech first (`language_runs`), and each run of one language is transcribed
on its own. A video in a single language is still transcribed in one go.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .hub import retry
from .media import decode_audio
from .segments import Segment, Word

SAMPLE_RATE = 16000  # what Whisper expects
DETECTOR = "base"  # small Whisper model used only to identify the language of each speech region
EDGE = 1.0  # at most this much audio is kept around a run when it is cut out (never past half the pause)
# A language counts as spoken in the video when it fills this share of the speech (summed detection probabilities)…
MAIN_SHARE = 0.15
# …or when one stretch of at least SURE_SECONDS is detected this surely (a short quote in another language).
SURE, SURE_SECONDS = 0.9, 2.0
# A region whose best guess is none of the video's languages, at least CHECK_SECONDS long, is heard again by the
# transcription model; if it is this sure of a language, the region keeps it (a foreign line in a film).
CHECK_SECONDS, CHECK_SURE = 1.5, 0.85
# NVIDIA's libraries missing or broken: Whisper picks the card ("auto") and fails on first use (cuBLAS/cuDNN DLLs).
_GPU_ERROR = re.compile(r"cublas|cudnn|cudart|nvrtc|cuda", re.I)
_gpu_failed = False  # the card failed once in this run of the program: use the processor from now on (gpu.py resets)


def gpu_error(exc: BaseException) -> bool:
    return bool(_GPU_ERROR.search(str(exc)))


def merge_runs(pieces: list[tuple[float, float, str, float]]) -> list[tuple[float, float, str]]:
    """Join consecutive (start, end, language, probability) pieces of the same language into runs.

    A piece whose detection is unsure (< 0.5) takes the language of the run before it (or after it, at the start).
    """
    known = [lang if prob >= 0.5 else "" for _, _, lang, prob in pieces]
    for i in range(len(known)):  # unsure → previous language
        if not known[i] and i:
            known[i] = known[i - 1]
    for i in range(len(known) - 2, -1, -1):  # still unsure at the start → next language
        if not known[i]:
            known[i] = known[i + 1]
    runs: list[tuple[float, float, str]] = []
    for (start, end, *_), lang in zip(pieces, known, strict=True):
        lang = lang or "en"
        if runs and runs[-1][2] == lang:
            runs[-1] = (runs[-1][0], end, lang)
        else:
            runs.append((start, end, lang))
    return runs


def video_languages(pieces: list[tuple[float, float, dict[str, float]]]) -> set[str]:
    """The languages really spoken in a video, from per-region detections [(start, end, {language: probability})].

    Whisper's detector guesses wildly on some regions of clear speech (real Hebrew recordings: regions called
    Italian 0.74, French 0.68, Latvian 0.50 — measured 2026-10-18), and a region transcribed in the wrong language
    comes out as gibberish. Such stray guesses are weak and few, so they never add up to a real share of the speech.
    """
    share: Counter[str] = Counter()
    total = 0.0
    sure: set[str] = set()
    for start, end, probs in pieces:
        seconds = end - start
        total += seconds
        for lang, prob in probs.items():
            share[lang] += seconds * prob
        lang, prob = max(probs.items(), key=lambda kv: kv[1], default=("", 0.0))
        if prob >= SURE and seconds >= SURE_SECONDS:
            sure.add(lang)
    spoken = {lang for lang, value in share.items() if value >= MAIN_SHARE * total} | sure
    return spoken or ({share.most_common(1)[0][0]} if share else set())


def language_runs(detector, samples, checker=None) -> list[tuple[float, float, str]]:
    """Stretches of the audio in one language each: [(start_s, end_s, language)].

    The language is detected for EVERY speech region (a sentence or two): Whisper's language detection mostly hears
    the start of what it is given, so a 20-s piece that began in French and ended in English was called French and
    its English lines were mislabelled (measured 2026-10-16). `detector` is a small Whisper model ("base"): it
    identified all 19 regions of two mixed test clips correctly, at ~0.3 s per region on CPU. Each region then gets
    the most likely of the languages spoken in the whole video (`video_languages`), never a stray guess.

    Except a foreign line: a region that "base" doesn't place in one of the video's languages is heard again by
    `checker` (the bigger transcription model) and keeps the language it is sure of. Spanish lines in an English film
    under noise: "base" said Portuguese 0.24 and the line was transcribed as English nonsense; "small" said Spanish
    0.93 (measured 2026-10-30, docs/RESEARCH.md).
    """
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    regions = get_speech_timestamps(samples, VadOptions(min_silence_duration_ms=300, max_speech_duration_s=15))
    detected = []
    for r in regions:
        lang, prob, all_probs = detector.detect_language(audio=samples[r["start"]:r["end"]])
        probs = dict(all_probs or [(lang, prob)])
        detected.append((r["start"] / SAMPLE_RATE, r["end"] / SAMPLE_RATE, probs))
    spoken = video_languages(detected)
    pieces = []
    for start, end, probs in detected:
        guess = max(probs, key=probs.get, default="")
        if checker is not None and guess not in spoken and end - start >= CHECK_SECONDS:
            heard, sure, _ = checker.detect_language(audio=samples[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)])
            if sure >= CHECK_SURE:
                pieces.append((start, end, heard, 1.0))
                continue
        lang = max(spoken, key=lambda language: probs.get(language, 0.0))
        among = sum(probs.get(language, 0.0) for language in spoken)
        pieces.append((start, end, lang, probs.get(lang, 0.0) / among if among else 0.0))
    return merge_runs(pieces)


def transcribe(
    audio_wav: Path, model_size: str = "small", device: str = "auto", progress=None, info_out: dict | None = None
) -> list[Segment]:
    """Return Whisper segments with word timings for an audio file in any language(s).

    `progress(fraction)` is called with 0..1 as transcription advances, if given.
    `info_out`, if given, receives {"language": main language, "languages": all languages by speaking time}.
    An NVIDIA card whose libraries are missing (ADR-034) never stops the dub: it goes on with the processor.
    """
    global _gpu_failed
    if device != "cpu" and not _gpu_failed:
        try:
            return _transcribe(audio_wav, model_size, device, progress, info_out)
        except Exception as exc:
            if not gpu_error(exc):
                raise
            _gpu_failed = True
            print(f"Видеокарта не готова ({str(exc).splitlines()[0]}) — распознаю речь на процессоре.", flush=True)
    return _transcribe(audio_wav, model_size, "cpu", progress, info_out)


def _transcribe(audio_wav: Path, model_size: str, device: str, progress, info_out: dict | None) -> list[Segment]:
    from faster_whisper import WhisperModel

    compute_type = "int8" if device in ("auto", "cpu") else "float16"
    model = retry(lambda: WhisperModel(model_size, device=device, compute_type=compute_type))  # downloads on first use
    where = getattr(getattr(model, "model", None), "device", device)  # what "auto" chose
    print(f"Распознаю речь: {'видеокарта' if where == 'cuda' else 'процессор'} ({where})", flush=True)
    # Decode with our own ffmpeg call and pass samples: faster-whisper's PyAV-based file loading breaks with
    # some PyAV versions (e.g. av 19 rejects the `metadata_errors` argument faster-whisper 1.2 passes).
    samples = decode_audio(audio_wav, SAMPLE_RATE)
    total = len(samples) / SAMPLE_RATE
    detector = retry(lambda: WhisperModel(DETECTOR, device=device, compute_type=compute_type))
    runs = language_runs(detector, samples, checker=model)

    spoken: Counter[str] = Counter()
    for start, end, lang in runs:
        spoken[lang] += end - start
    if info_out is not None:
        info_out["languages"] = [lang for lang, _ in spoken.most_common()]
        info_out["language"] = info_out["languages"][0] if spoken else ""

    if len(spoken) <= 1:  # one language: transcribe everything at once (best context)
        language = next(iter(spoken), None)
        pieces = [(0.0, total, language)]
    else:
        # The speech detector's bounds are tight: with 0.2 s the first words of a run were lost (FLEURS en+fr,
        # 2026-10-18). Reach into the pause before and after, but never past its middle (the other language).
        pieces = []
        for i, (s, e, lang) in enumerate(runs):
            before = (s - runs[i - 1][1]) / 2 if i else s
            after = (runs[i + 1][0] - e) / 2 if i + 1 < len(runs) else total - e
            pieces.append((s - min(EDGE, before), e + min(EDGE, after), lang))

    segments: list[Segment] = []
    for start, end, language in pieces:
        chunk = samples[int(start * SAMPLE_RATE): int(end * SAMPLE_RATE)]
        # Word timings let the pipeline cut real sentences with speech-only bounds (segments.split_into_units).
        raw_segments, _ = model.transcribe(
            chunk, language=language, vad_filter=True, beam_size=5, word_timestamps=True
        )
        for s in raw_segments:  # a generator: transcription happens while iterating
            lang = language or ""
            words = [Word(start + float(w.start), start + float(w.end), w.word, lang) for w in (s.words or [])]
            segments.append(Segment(start=start + float(s.start), end=start + float(s.end), text=s.text.strip(),
                                    words=words, lang=lang))
            if progress and total:
                progress(min(1.0, (start + float(s.end)) / total))
    return segments


def reader(model_size: str = "small", device: str = "auto"):
    """`read(clip, lang)` -> what Whisper hears in a short clip (the original voice's listen-back check, clone.py).

    The model loads on the first clip; on the card when it works, else the processor (as `transcribe`)."""
    from faster_whisper import WhisperModel

    models: dict[str, object] = {}

    def model_on(where: str):
        if where not in models:
            compute_type = "int8" if where in ("auto", "cpu") else "float16"
            models[where] = retry(lambda: WhisperModel(model_size, device=where, compute_type=compute_type))
        return models[where]

    def read(clip: Path, lang: str) -> str:
        global _gpu_failed
        samples = decode_audio(clip, SAMPLE_RATE)
        if device != "cpu" and not _gpu_failed:
            try:
                segments, _ = model_on(device).transcribe(samples, language=lang, beam_size=5)
                return " ".join(s.text.strip() for s in segments)
            except Exception as exc:
                if not gpu_error(exc):
                    raise
                _gpu_failed = True
        segments, _ = model_on("cpu").transcribe(samples, language=lang, beam_size=5)
        return " ".join(s.text.strip() for s in segments)

    return read

