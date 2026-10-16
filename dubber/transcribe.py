"""Stage 2 — English speech to timed text with faster-whisper."""

from __future__ import annotations

from pathlib import Path

from .hub import retry
from .media import decode_audio
from .segments import Segment, Word

SAMPLE_RATE = 16000  # what Whisper expects


def transcribe(audio_wav: Path, model_size: str = "small", device: str = "auto", progress=None) -> list[Segment]:
    """Return Whisper segments for an English audio file.

    `progress(fraction)` is called with 0..1 as transcription advances, if given.
    """
    from faster_whisper import WhisperModel

    compute_type = "int8" if device in ("auto", "cpu") else "float16"
    model = retry(lambda: WhisperModel(model_size, device=device, compute_type=compute_type))  # downloads on first use
    # Decode with our own ffmpeg call and pass samples: faster-whisper's PyAV-based file loading breaks with
    # some PyAV versions (e.g. av 19 rejects the `metadata_errors` argument faster-whisper 1.2 passes).
    samples = decode_audio(audio_wav, SAMPLE_RATE)
    # Word timings let the pipeline cut real sentences with speech-only bounds (segments.split_into_units).
    raw_segments, info = model.transcribe(
        samples, language="en", vad_filter=True, beam_size=5, word_timestamps=True
    )

    segments: list[Segment] = []
    for s in raw_segments:  # a generator: transcription happens while iterating
        words = [Word(float(w.start), float(w.end), w.word) for w in (getattr(s, "words", None) or [])]
        segments.append(Segment(start=float(s.start), end=float(s.end), text=s.text.strip(), words=words))
        if progress and info.duration:
            progress(min(1.0, s.end / info.duration))
    return segments
