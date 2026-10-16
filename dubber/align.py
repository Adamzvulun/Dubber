"""Stage 5 — place each Russian clip at its segment's time, speeding it up when it is too long."""

from __future__ import annotations

from pathlib import Path

from .media import decode_audio, write_wav
from .segments import Segment

SAMPLE_RATE = 24000
TAIL_ALLOWANCE = 1.0  # seconds the last clip may run past its segment end


def atempo_filter(speed: float) -> str | None:
    """ffmpeg atempo filter for a speed-up factor (None when no change is needed)."""
    if speed <= 1.01:
        return None
    return f"atempo={speed:.4f}"


def plan_speed(clip_seconds: float, slot_seconds: float, max_speedup: float) -> float:
    """How much to speed a clip up so it fits its slot, capped at `max_speedup`."""
    if slot_seconds <= 0 or clip_seconds <= slot_seconds:
        return 1.0
    return min(clip_seconds / slot_seconds, max_speedup)


def build_track(
    segments: list[Segment],
    clips: list[Path | None],
    total_seconds: float,
    out_wav: Path,
    max_speedup: float = 1.5,
    progress=None,
) -> Path:
    """Mix all clips into one mono WAV of length `total_seconds`.

    Each clip may use the time until the next segment starts (its "slot"). If it is still too long
    after the capped speed-up, it starts on time and later clips are pushed back so voices never overlap.
    """
    import numpy as np

    track = np.zeros(int(total_seconds * SAMPLE_RATE) + 1, dtype=np.float32)
    cursor = 0  # first free sample
    for i, (seg, clip) in enumerate(zip(segments, clips, strict=True)):
        if clip is None or not clip.exists():
            continue
        next_start = segments[i + 1].start if i + 1 < len(segments) else seg.end + TAIL_ALLOWANCE
        slot = max(seg.end, next_start) - seg.start

        audio = decode_audio(clip, SAMPLE_RATE)
        speed = plan_speed(len(audio) / SAMPLE_RATE, slot, max_speedup)
        if speed > 1.01:
            audio = decode_audio(clip, SAMPLE_RATE, atempo_filter(speed))

        start = max(int(seg.start * SAMPLE_RATE), cursor)
        end = start + len(audio)
        if end > len(track):
            track = np.concatenate([track, np.zeros(end - len(track), dtype=np.float32)])
        track[start:end] += audio
        cursor = end
        if progress:
            progress((i + 1) / len(segments))

    return write_wav(track, out_wav, SAMPLE_RATE)
