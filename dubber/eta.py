"""A rough "time left" for a running dub, shown on the job card.

The pipeline reports one overall fraction with fixed stage weights (pipeline.STAGES), but how long each stage really
takes depends on the PC (Whisper on a CPU dominates) and on what is already cached. So:
- `Tracker` records when each stage started and how far it is;
- each stage has a "share" of the total time: the defaults below, blended with what finished dubs measured on this PC
  (`record` / `load_shares`, last HISTORY jobs in work/stage_times.json);
- time left = (seconds of real work so far / share of work done) × share still to do. Stages that finished almost
  instantly (taken from the cache after a resume) are left out, so they don't make the pace look faster than it is.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

DEFAULT_SHARES = {"download": 0.08, "transcribe": 0.45, "translate": 0.07, "tts": 0.25, "align": 0.05, "mux": 0.10,
                  "separate": 0.30}  # optional (removing the original voice), on top of the others, which add up to 1
HISTORY = 10  # finished jobs kept for learning
PRIOR = 2  # the defaults count as this many jobs when blended with measurements
MIN_JOB_SECONDS = 60  # shorter jobs (mostly cached) say little about the stages
CACHED = 2.0  # a stage that took less than this was (almost) all cached
MIN_WORK_SECONDS = 15  # no estimate before this much real work…
MIN_DONE_SHARE = 0.03  # …or this share of it


class Tracker:
    """Stage timings of one job, fed from the pipeline's progress reports."""

    def __init__(self, stages: list[tuple[str, float]], clock: Callable[[], float] = time.monotonic):
        self._weights = dict(stages)
        self._bases, base = {}, 0.0
        for key, weight in stages:
            self._bases[key] = base
            base += weight
        self._order = [key for key, _ in stages]
        self._clock = clock
        self._started: dict[str, float] = {}
        self._finished: dict[str, float] = {}  # stage → seconds
        self.current = ""
        self.fraction = 0.0  # of the current stage

    def update(self, key: str, overall: float) -> None:
        if key not in self._weights:
            return
        now = self._clock()
        if key != self.current:
            if self.current:
                self._finished[self.current] = now - self._started[self.current]
            self.current = key
            self._started[key] = now
        weight = self._weights[key]
        self.fraction = min(1.0, max(0.0, (overall - self._bases[key]) / weight)) if weight else 1.0

    def stage_seconds(self) -> dict[str, float]:
        """Seconds per stage so far (the current one until now)."""
        out = dict(self._finished)
        if self.current:
            out[self.current] = self._clock() - self._started[self.current]
        return out

    def eta(self, shares: dict[str, float]) -> float | None:
        """Seconds left, or None while there is too little real work to judge the pace."""
        if not self.current:
            return None
        work = done = 0.0
        for key, seconds in self._finished.items():
            if seconds >= CACHED:
                work += seconds
                done += shares.get(key, 0.0)
        work += self._clock() - self._started[self.current]
        share = shares.get(self.current, 0.0)
        done += share * self.fraction
        position = self._order.index(self.current)
        left = share * (1 - self.fraction) + sum(shares.get(k, 0.0) for k in self._order[position + 1:])
        if work < MIN_WORK_SECONDS or done < MIN_DONE_SHARE:
            return None
        return work / done * left


def record(path: Path, seconds: dict[str, float]) -> None:
    """Remember a finished job's stage timings (only jobs long enough to learn from)."""
    if sum(seconds.values()) < MIN_JOB_SECONDS:
        return
    history = _read(path)
    history.append({k: round(v, 2) for k, v in seconds.items()})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history[-HISTORY:]), encoding="utf-8")
    except OSError:
        pass  # the estimate just stays on the defaults


def load_shares(path: Path) -> dict[str, float]:
    """Stage shares for this PC: the defaults blended with the measured jobs (each job's stages sum to 1)."""
    history = [job for job in _read(path) if sum(job.values()) >= MIN_JOB_SECONDS]
    if not history:
        return dict(DEFAULT_SHARES)
    blended = {}
    for key, default in DEFAULT_SHARES.items():
        # An optional stage ("separate") is learned only from the jobs that ran it.
        jobs = [job for job in history if key in job] if key == "separate" else history
        measured = sum(job.get(key, 0.0) / _core(job) for job in jobs)
        blended[key] = (PRIOR * default + measured) / (PRIOR + len(jobs))
    total = sum(value for key, value in blended.items() if key != "separate")  # the stages every job runs sum to 1
    return {key: value / total for key, value in blended.items()}


def _core(job: dict[str, float]) -> float:
    """Seconds of the stages every job runs (shares are relative to these, so the optional one fits on top)."""
    return sum(v for k, v in job.items() if k != "separate") or 1.0


def _read(path: Path) -> list[dict[str, float]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [job for job in data if isinstance(job, dict)] if isinstance(data, list) else []
