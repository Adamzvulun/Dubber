import json

from dubber import eta

STAGES = [("download", 0.10), ("transcribe", 0.40), ("translate", 0.10), ("tts", 0.20), ("align", 0.10),
          ("mux", 0.10)]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def run_stage(tracker, clock, key, seconds, steps=4):
    """Report a stage the way the pipeline does: start (0), then evenly up to done."""
    base = sum(w for k, w in STAGES[:[k for k, _ in STAGES].index(key)])
    weight = dict(STAGES)[key]
    for i in range(steps + 1):
        tracker.update(key, base + weight * i / steps)
        if i < steps:
            clock.now += seconds / steps


def test_no_estimate_at_first():
    clock = Clock()
    t = eta.Tracker(STAGES, clock)
    t.update("download", 0.0)
    clock.now += 5
    t.update("download", 0.05)
    assert t.eta(eta.DEFAULT_SHARES) is None  # under 15 s of work


def test_estimate_follows_the_measured_pace():
    clock = Clock()
    t = eta.Tracker(STAGES, clock)
    shares = {"download": 0.1, "transcribe": 0.4, "translate": 0.1, "tts": 0.2, "align": 0.1, "mux": 0.1}
    run_stage(t, clock, "download", 20)  # 20 s for a 0.1 share → 200 s total → 180 s left
    t.update("transcribe", 0.10)
    assert abs(t.eta(shares) - 180) < 1
    run_stage(t, clock, "transcribe", 80)
    assert abs(t.eta(shares) - 100) < 1  # same pace: half of the work left


def test_cached_stages_do_not_distort_the_pace():
    # A resumed job: download and transcription come from the cache (instant).
    clock = Clock()
    t = eta.Tracker(STAGES, clock)
    shares = {"download": 0.1, "transcribe": 0.4, "translate": 0.1, "tts": 0.2, "align": 0.1, "mux": 0.1}
    run_stage(t, clock, "download", 0.2)
    run_stage(t, clock, "transcribe", 0.3)
    run_stage(t, clock, "translate", 30)  # 30 s for a 0.1 share
    t.update("tts", 0.6)
    assert abs(t.eta(shares) - 120) < 2  # tts + align + mux = 0.4 share at 300 s per share
    assert t.stage_seconds()["download"] < 1


def test_shares_learned_from_this_pc_blend_with_defaults(tmp_path):
    path = tmp_path / "stage_times.json"
    assert eta.load_shares(path) == eta.DEFAULT_SHARES
    slow_whisper = {"download": 10, "transcribe": 300, "translate": 10, "tts": 60, "align": 10, "mux": 10}
    for _ in range(12):
        eta.record(path, slow_whisper)
    assert len(json.loads(path.read_text())) == eta.HISTORY  # capped
    shares = eta.load_shares(path)
    assert abs(sum(v for k, v in shares.items() if k not in eta.OPTIONAL) - 1) < 1e-6
    assert shares["transcribe"] > eta.DEFAULT_SHARES["transcribe"] + 0.15  # learned: Whisper dominates here
    eta.record(path, {"download": 1, "transcribe": 2})  # too short to learn from: ignored
    assert eta.load_shares(path) == shares


def test_optional_voice_removal_learned_only_from_jobs_that_ran_it(tmp_path):
    path = tmp_path / "stage_times.json"
    plain = {"download": 10, "transcribe": 100, "translate": 10, "tts": 50, "align": 10, "mux": 20}
    for _ in range(4):
        eta.record(path, plain)
    without = eta.load_shares(path)["separate"]
    for _ in range(4):
        eta.record(path, plain | {"separate": 400})  # this PC separates slowly
    assert eta.load_shares(path)["separate"] > without + 0.5


def test_broken_history_falls_back_to_defaults(tmp_path):
    path = tmp_path / "stage_times.json"
    path.write_text("{not json")
    assert eta.load_shares(path) == eta.DEFAULT_SHARES
    eta.record(path, {"download": 30, "transcribe": 100, "translate": 5, "tts": 40, "align": 5, "mux": 10})
    assert len(json.loads(path.read_text())) == 1


def test_the_original_voice_learns_its_own_share(tmp_path):
    """«Оригинал» (OmniVoice on the card) and the Edge voice take very different times: learned apart."""
    from dubber import eta

    history = tmp_path / "stage_times.json"
    edge = {"download": 10, "transcribe": 60, "translate": 10, "tts": 20, "align": 5, "mux": 15}
    for _ in range(3):
        eta.record(history, edge)
    eta.record(history, {**{k: v for k, v in edge.items() if k != "tts"}, "separate": 40, "tts_clone": 300})
    shares = eta.load_shares(history)
    assert shares["tts_clone"] > 0.4 > 0.25 > shares["tts"]  # one long clone job already moves it
    core = sum(v for k, v in shares.items() if k not in eta.OPTIONAL)
    assert abs(core - 1.0) < 1e-9
