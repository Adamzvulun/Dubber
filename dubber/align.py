"""Stage 5 — place each Russian clip at its line's start time and mix them into one track.

The voice already speaks at the planned pace (`timing.plan_rates` + Edge TTS rate), so a clip normally fits.
When it still runs over (rates are capped), it gets a small time-stretch; anything left over pushes the next
lines back so voices never overlap.
"""

from __future__ import annotations

from pathlib import Path

from .media import decode_audio, write_wav
from .segments import Segment
from .timing import slots

SAMPLE_RATE = 24000
MAX_CORRECTION = 1.1  # at most 10% extra time-stretch after synthesis (it sounds worse than a faster voice)
SILENCE = 0.01  # samples quieter than 1% of the clip's peak count as silence
PAD = 0.03  # seconds of silence kept around trimmed speech


def trim_silence(audio):
    """Cut the silence Edge TTS puts around every clip (measured ~0.25 s before and ~0.9 s after the speech).

    Left in, it makes each line start late and counts as speech when fitting lines into the speaker's timing.
    """
    import numpy as np

    if len(audio) == 0:
        return audio
    loud = np.flatnonzero(np.abs(audio) > SILENCE * float(np.abs(audio).max()))
    if len(loud) == 0:
        return audio[:0]
    pad = int(PAD * SAMPLE_RATE)
    return audio[max(0, loud[0] - pad): loud[-1] + 1 + pad]


def speech_seconds(clip: Path) -> float:
    """Length of the speech in a clip, without the silence around it."""
    return len(trim_silence(decode_audio(clip, SAMPLE_RATE))) / SAMPLE_RATE


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
    max_correction: float = MAX_CORRECTION,
    progress=None,
    report: list[dict] | None = None,
) -> Path:
    """Mix all clips into one mono WAV of length `total_seconds`.

    If `report` is given, one dict per spoken line is appended: when it was meant to start, how late it actually
    started (pushed back by an over-long previous line), and the extra time-stretch it needed.
    """
    import numpy as np

    track = np.zeros(int(total_seconds * SAMPLE_RATE) + 1, dtype=np.float32)
    cursor = 0  # first free sample
    for i, (seg, clip, slot) in enumerate(zip(segments, clips, slots(segments), strict=True)):
        if clip is None or not clip.exists():
            continue
        audio = trim_silence(decode_audio(clip, SAMPLE_RATE))
        speed = plan_speed(len(audio) / SAMPLE_RATE, slot, max_correction)
        if speed > 1.01:
            audio = trim_silence(decode_audio(clip, SAMPLE_RATE, atempo_filter(speed)))

        start = max(int(seg.start * SAMPLE_RATE), cursor)
        end = start + len(audio)
        if end > len(track):
            track = np.concatenate([track, np.zeros(end - len(track), dtype=np.float32)])
        track[start:end] += audio
        cursor = end
        if report is not None:
            report.append({
                "index": i,
                "start": round(seg.start, 2),
                "delay": round(start / SAMPLE_RATE - seg.start, 2),
                "stretch": round(speed, 3),
                "spoken": round(len(audio) / SAMPLE_RATE, 2),
                "slot": round(slot, 2),
            })
        if progress:
            progress((i + 1) / len(segments))

    return write_wav(track, out_wav, SAMPLE_RATE)
