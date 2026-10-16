"""Stage 2 — English speech to timed text with faster-whisper."""

from __future__ import annotations

from pathlib import Path

from .segments import Segment


def transcribe(audio_wav: Path, model_size: str = "small", device: str = "auto", progress=None) -> list[Segment]:
    """Return Whisper segments for an English audio file.

    `progress(fraction)` is called with 0..1 as transcription advances, if given.
    """
    from faster_whisper import WhisperModel

    compute_type = "int8" if device in ("auto", "cpu") else "float16"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    raw_segments, info = model.transcribe(str(audio_wav), language="en", vad_filter=True, beam_size=5)

    segments: list[Segment] = []
    for s in raw_segments:  # a generator: transcription happens while iterating
        segments.append(Segment(start=float(s.start), end=float(s.end), text=s.text.strip()))
        if progress and info.duration:
            progress(min(1.0, s.end / info.duration))
    return segments
