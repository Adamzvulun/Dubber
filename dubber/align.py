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
# Every line fades in and out, and keeps its soft tail (the last syllable's release, a breath): cut at the speech's
# edges, lines started and stopped hard — "very rough chops between sentences, harsh on the ear" (Adam, 2026-10-29).
FADE_IN = 0.015
FADE_OUT = 0.08
TAIL = 0.12  # seconds of the quiet tail kept after the speech (it may run under the next line's start)


def trim_silence(audio, tail: float = PAD):
    """Cut the silence Edge TTS puts around every clip (measured ~0.25 s before and ~0.9 s after the speech).

    Left in, it makes each line start late and counts as speech when fitting lines into the speaker's timing.
    `tail`: seconds kept after the speech.
    """
    import numpy as np

    if len(audio) == 0:
        return audio
    loud = np.flatnonzero(np.abs(audio) > SILENCE * float(np.abs(audio).max()))
    if len(loud) == 0:
        return audio[:0]
    pad = int(PAD * SAMPLE_RATE)
    return audio[max(0, loud[0] - pad): loud[-1] + 1 + int(tail * SAMPLE_RATE)]


def fade(audio):
    """Fade a line in and out (a raised-cosine curve: no click, no sudden stop)."""
    import numpy as np

    audio = audio.copy()
    for seconds, edge in ((FADE_IN, slice(None)), (FADE_OUT, slice(None, None, -1))):
        n = min(int(seconds * SAMPLE_RATE), len(audio) // 2)
        if n:
            curve = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))).astype(np.float32)
            audio[edge][:n] *= curve
    return audio


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
        raw = decode_audio(clip, SAMPLE_RATE)
        speed = plan_speed(len(trim_silence(raw)) / SAMPLE_RATE, slot, max_correction)
        if speed > 1.01:
            raw = decode_audio(clip, SAMPLE_RATE, atempo_filter(speed))
        spoken = len(trim_silence(raw))
        # placed with its soft tail and faded, but the next line may start where the speech ends
        sound = fade(trim_silence(raw, tail=TAIL))

        start = max(int(seg.start * SAMPLE_RATE), cursor)
        end = start + len(sound)
        if end > len(track):
            track = np.concatenate([track, np.zeros(end - len(track), dtype=np.float32)])
        track[start:end] += sound
        cursor = start + spoken
        if report is not None:
            report.append({
                "index": i,
                "start": round(seg.start, 2),
                "delay": round(start / SAMPLE_RATE - seg.start, 2),
                "stretch": round(speed, 3),
                "spoken": round(spoken / SAMPLE_RATE, 2),
                "slot": round(slot, 2),
            })
        if progress:
            progress((i + 1) / len(segments))

    return write_wav(track, out_wav, SAMPLE_RATE)
