"""Stage 2 — speech (any language, even several in one video) to timed text with faster-whisper.

Whisper transcribes in ONE language per 30-s window and silently drops speech in another language: forcing English
lost a whole French passage, and auto-detection lost the English intro before it (measured 2026-10-16). So the
language is detected for each stretch of speech first (`language_runs`), and each run of one language is transcribed
on its own. A video in a single language is still transcribed in one go.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .hub import retry
from .media import decode_audio
from .segments import Segment, Word

SAMPLE_RATE = 16000  # what Whisper expects
DETECTOR = "base"  # small Whisper model used only to identify the language of each speech region
EDGE = 0.2  # seconds of audio kept around a run when it is cut out


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


def language_runs(detector, samples) -> list[tuple[float, float, str]]:
    """Stretches of the audio in one language each: [(start_s, end_s, language)].

    The language is detected for EVERY speech region (a sentence or two): Whisper's language detection mostly hears
    the start of what it is given, so a 20-s piece that began in French and ended in English was called French and
    its English lines were mislabelled (measured 2026-10-16). `detector` is a small Whisper model ("base"): it
    identified all 19 regions of two mixed test clips correctly, at ~0.3 s per region on CPU.
    """
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    regions = get_speech_timestamps(samples, VadOptions(min_silence_duration_ms=300, max_speech_duration_s=15))
    pieces = []
    for r in regions:
        lang, prob, _ = detector.detect_language(audio=samples[r["start"]:r["end"]])
        pieces.append((r["start"] / SAMPLE_RATE, r["end"] / SAMPLE_RATE, lang, float(prob)))
    return merge_runs(pieces)


def transcribe(
    audio_wav: Path, model_size: str = "small", device: str = "auto", progress=None, info_out: dict | None = None
) -> list[Segment]:
    """Return Whisper segments with word timings for an audio file in any language(s).

    `progress(fraction)` is called with 0..1 as transcription advances, if given.
    `info_out`, if given, receives {"language": main language, "languages": all languages by speaking time}.
    """
    from faster_whisper import WhisperModel

    compute_type = "int8" if device in ("auto", "cpu") else "float16"
    model = retry(lambda: WhisperModel(model_size, device=device, compute_type=compute_type))  # downloads on first use
    # Decode with our own ffmpeg call and pass samples: faster-whisper's PyAV-based file loading breaks with
    # some PyAV versions (e.g. av 19 rejects the `metadata_errors` argument faster-whisper 1.2 passes).
    samples = decode_audio(audio_wav, SAMPLE_RATE)
    total = len(samples) / SAMPLE_RATE
    detector = retry(lambda: WhisperModel(DETECTOR, device=device, compute_type=compute_type))
    runs = language_runs(detector, samples)

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
        pieces = [(max(0.0, s - EDGE), min(total, e + EDGE), lang) for s, e, lang in runs]

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
