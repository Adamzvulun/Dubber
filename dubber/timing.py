"""Plan how fast the Russian voice speaks each line so the dub keeps the speaker's pace.

Research and measurements: docs/RESEARCH.md "Dub timing". In short: natural Russian speech runs ~1.4-1.5x longer
than the English, so the voice must speak faster. Doing that inside the TTS engine (Edge `rate`) sounds better than
time-stretching afterwards, and one steady pace per video sounds better than a different speed on every line.
"""

from __future__ import annotations

from statistics import median

from .segments import Segment

BREATH = 0.15  # seconds of silence kept before the next line starts
TAIL_ALLOWANCE = 1.0  # seconds the last line may run past the end of the speech
MIN_RATE = 0.9  # the voice may slow down a little when the Russian is short
BAND = 0.12  # a line's own pace may differ from the video's pace by at most ±12% (unless it must, to fit)
STEP = 0.08  # neighbouring lines differ in pace by at most this much (smoothing)


def slots(segments: list[Segment]) -> list[float]:
    """Seconds each line may use: until shortly before the next line starts (never less than its own speech)."""
    out = []
    for i, seg in enumerate(segments):
        if i + 1 < len(segments):
            limit = segments[i + 1].start - BREATH
        else:
            limit = seg.end + TAIL_ALLOWANCE
        out.append(max(seg.duration, limit - seg.start))
    return out


def plan_rates(segments: list[Segment], natural: list[float | None], max_rate: float) -> list[float]:
    """Speaking-rate factor per line (1.0 = the voice's natural speed, 1.3 = 30% faster).

    `natural[i]` is the length in seconds of line i spoken at natural speed (None = nothing to say).
    1. The video's base pace is the median of "Russian length / English speech length": the dub then talks at the
       speaker's own pace, finishing each line about when the speaker does.
    2. Each line follows its own ratio only within ±BAND of the base, so the pace stays steady.
    3. A line is sped up further only if it would not fit before the next line (using the pause after it).
    4. Neighbouring lines differ by at most STEP, so the pace never jumps from line to line.
    """
    budget = slots(segments)
    ratios = [n / s.duration for s, n in zip(segments, natural, strict=True) if n and s.duration > 0.3]
    base = min(max(median(ratios), MIN_RATE), max_rate) if ratios else 1.0

    rates: list[float] = []
    for seg, n, slot in zip(segments, natural, budget, strict=True):
        if not n:
            rates.append(base)
            continue
        own = n / seg.duration if seg.duration > 0.3 else base
        rate = min(max(own, base * (1 - BAND)), base * (1 + BAND))
        rate = max(rate, n / slot)  # must fit before the next line
        rates.append(min(max(rate, MIN_RATE), max_rate))

    # Smooth: lift a line that is much slower than a neighbour (lifting never breaks the fit).
    for i in range(1, len(rates)):
        rates[i] = min(max(rates[i], rates[i - 1] - STEP), max_rate)
    for i in range(len(rates) - 2, -1, -1):
        rates[i] = min(max(rates[i], rates[i + 1] - STEP), max_rate)
    return rates


def edge_rate(rate: float) -> str:
    """Edge TTS `rate` string for a factor: 1.35 -> "+35%" (measured: duration = natural / factor)."""
    return f"{round((rate - 1) * 100):+d}%"
