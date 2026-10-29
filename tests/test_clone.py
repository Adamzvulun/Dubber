"""The original-voice dub (clone.py) with a stand-in model; the real OmniVoice is checked by hand (STATUS)."""

import subprocess

import numpy as np
import pytest

from dubber import clone
from dubber.media import decode_audio, run_ffmpeg
from dubber.segments import Segment


def seg(start, end, text="hello there", ru="привет всем"):
    return Segment(start=start, end=end, text=text, ru=ru)


def test_short_lines_borrow_neighbours_across_short_pauses():
    lines = [seg(0, 1), seg(1.3, 2.0), seg(2.2, 3.5), seg(8, 9), seg(9.2, 30), seg(31, 35)]
    assert clone.reference_lines(lines, 0) == [0, 1, 2]  # 1 s alone is too little
    assert clone.reference_lines(lines, 2) == [0, 1, 2]  # the shorter pause first
    # 5 s of silence before line 3 (could be another speaker), and line 4 would make it longer than MAX_REF
    assert clone.reference_lines(lines, 3) == [3]
    # a 20.8-s line can't be a reference itself: the nearest line that fits is used
    assert clone.reference_lines(lines, 4) == [3]
    assert clone.reference_lines(lines, 5) == [5]


def fake_run(stdout="", code=0):
    def run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, code, stdout=stdout, stderr="")
    return run


def test_gpu_check():
    assert clone.gpu_info(fake_run("NVIDIA GeForce RTX 3070, 8192\n")) == {"name": "NVIDIA GeForce RTX 3070",
                                                                           "vram_gb": 8.0}
    assert clone.gpu_info(fake_run(code=9)) is None

    def missing(cmd, **kwargs):
        raise FileNotFoundError("nvidia-smi")
    assert clone.gpu_info(missing) is None
    assert clone.status(fake_run("NVIDIA GeForce RTX 3070, 8192"))["gpu_ok"] is True
    assert clone.status(fake_run("NVIDIA GeForce GTX 1650, 4096"))["gpu_ok"] is False
    assert clone.status(missing)["gpu_ok"] is False
    assert not clone.supports("he") and clone.supports("ru")


class FakeEngine:
    """Speaks a 220 Hz tone exactly as long as asked; remembers what it was given."""

    def __init__(self, fail_batches=False):
        self.prompts, self.calls, self.fail_batches = [], [], fail_batches

    def prompt(self, audio, text):
        self.prompts.append((len(audio) / clone.SAMPLE_RATE, text))
        return {"text": text}

    def natural_seconds(self, text, prompt):
        return 0.1 * len(text)

    def speak(self, texts, prompts, durations, lang):
        if self.fail_batches and len(texts) > 1:
            raise RuntimeError("CUDA out of memory")
        self.calls.append((list(texts), list(durations), lang))
        return [0.01 * np.sin(np.arange(int(d * clone.SAMPLE_RATE)) / 10).astype(np.float32) for d in durations]

    def close(self):
        pass


@pytest.fixture
def vocals(tmp_path):
    path = tmp_path / "vocals.wav"
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=220:duration=12", "-ac", "2", "-ar", "44100", str(path)])
    return path


def test_lines_are_spoken_in_the_speakers_voice(tmp_path, vocals):
    lines = [seg(0.0, 3.2, "First sentence here.", "Первое предложение."),
             seg(3.6, 4.4, "Okay.", "Хорошо."),
             seg(4.6, 8.0, "Third one.", "—"),  # nothing to say: no clip
             seg(8.5, 11.5, "And the last.", "И последнее.")]
    engine, seen = FakeEngine(), []
    clips, rates = clone.synthesize(lines, vocals, "ru", tmp_path / "work" / "clips_original_ru", 1.6,
                                    engine=engine, progress=seen.append, batch=2)
    assert clips[2] is None and all(clips[i].exists() for i in (0, 1, 3))
    assert len(rates) == 4 and seen[-1] == 1.0
    assert [lang for *_, lang in engine.calls] == ["ru", "ru"]  # 3 lines, 2 per call
    # each clip lasts what the plan asked for, and is brought to the common loudness
    for i, clip in ((0, clips[0]), (3, clips[3])):
        audio = decode_audio(clip, clone.SAMPLE_RATE)
        planned = round(0.1 * len(lines[i].ru) / rates[i], 2)
        assert abs(len(audio) / clone.SAMPLE_RATE - planned) < 0.02
        assert abs(float(np.sqrt(np.mean(audio * audio))) - clone.LOUDNESS) < 0.01
    # the short line "Okay." borrowed a neighbour to reach a usable reference
    assert any("Okay." in text and len(text) > len("Okay.") for _, text in engine.prompts)

    again = FakeEngine()  # everything is cached: the model isn't asked again
    assert clone.synthesize(lines, vocals, "ru", tmp_path / "work" / "clips_original_ru", 1.6, engine=again)[0] == clips
    assert again.calls == []


def test_a_batch_that_fails_is_spoken_line_by_line(tmp_path, vocals):
    lines = [seg(0.0, 3.2, "One.", "Один."), seg(4.0, 7.5, "Two.", "Два.")]
    engine = FakeEngine(fail_batches=True)
    clips, _ = clone.synthesize(lines, vocals, "ar", tmp_path / "w" / "c", 1.6, engine=engine, batch=4)
    assert all(c.exists() for c in clips) and len(engine.calls) == 2


def test_syllables():
    assert clone.syllables("Прекрасно.") == 3
    assert clone.syllables("Où êtes-vous ?") == 4  # accented vowels count
    assert clone.syllables("你好吗") == 3 and clone.syllables("ありがとう") == 5
    assert clone.syllables("مرحبا بكم") == 4  # Arabic writes no short vowels: letters / 2
    assert clone.syllables("—") == 0


def test_a_line_is_never_asked_to_be_said_faster_than_people_can_speak(tmp_path, vocals):
    # Adam's dub, 2026-10-29: the model guessed ~0.15 s for whole words and lines in a crowded stretch were planned
    # 1.6x fast; told to fit that, the copied voice swallowed and warped them.
    class Hasty(FakeEngine):
        def natural_seconds(self, text, prompt):
            return 0.15

    lines = [seg(0.0, 3.2, "First sentence here.", "Первое предложение."),
             seg(3.6, 8.4, "Wonderful.", "Прекрасно."),
             seg(8.5, 11.5, "And the last.", "И последнее.")]
    engine = Hasty()
    clips, rates = clone.synthesize(lines, vocals, "ru", tmp_path / "w" / "c", 1.6, engine=engine)
    spoken = {text: d for texts, durations, _ in engine.calls for text, d in zip(texts, durations, strict=True)}
    for line, rate in zip(lines, rates, strict=True):
        floor = clone.min_seconds(line.ru)
        assert spoken[line.ru] >= floor - 0.01
        assert abs(rate - 0.15 / spoken[line.ru]) < 0.01  # timing.json shows the pace really asked for
    assert clone.min_seconds("Прекрасно.") >= 0.6


def test_lines_of_similar_length_share_a_model_call(tmp_path, vocals):
    lines = [seg(0, 2, "a", "Да."), seg(2.5, 9, "b", "Очень длинное предложение про всё на свете сразу."),
             seg(9.5, 11, "c", "Нет."), seg(11.5, 18, "d", "Ещё одно очень длинное предложение про всё подряд.")]
    engine = FakeEngine()
    clone.synthesize(lines, vocals, "ru", tmp_path / "w" / "c", 1.6, engine=engine, batch=2)
    assert sorted(sorted(texts) for texts, _, _ in engine.calls) == [
        sorted([lines[0].ru, lines[2].ru]), sorted([lines[1].ru, lines[3].ru])]


def test_the_batch_follows_the_cards_memory(tmp_path, vocals):
    assert clone.batch_for(16.0) > clone.batch_for(8.0) >= clone.batch_for(6.0) == clone.BATCH
    engine = FakeEngine()
    engine.batch = 3  # the engine's own suggestion (from the card's memory) is used when no batch is given
    lines = [seg(i * 2.0, i * 2.0 + 1.5, "x", f"Строка номер {i}.") for i in range(6)]
    clone.synthesize(lines, vocals, "ru", tmp_path / "w" / "c", 1.6, engine=engine)
    assert [len(texts) for texts, _, _ in engine.calls] == [3, 3]


def test_a_failing_batch_is_halved_not_spoken_one_by_one(tmp_path, vocals):
    class Small(FakeEngine):  # the card has room for 2 lines at once
        def speak(self, texts, prompts, durations, lang):
            if len(texts) > 2:
                raise RuntimeError("CUDA out of memory")
            return super().speak(texts, prompts, durations, lang)

    lines = [seg(i * 2.0, i * 2.0 + 1.5, "x", f"Строка номер {i}.") for i in range(8)]
    engine = Small()
    clips, _ = clone.synthesize(lines, vocals, "ru", tmp_path / "w" / "c", 1.6, engine=engine, batch=8)
    assert all(c.exists() for c in clips)
    assert [len(texts) for texts, _, _ in engine.calls] == [2, 2, 2, 2]


def test_installer_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(clone, "marker", lambda: tmp_path / "dubber-omnivoice")
    ran = []

    def run(cmd, **kwargs):
        ran.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    installer = clone.Installer(tmp_path / "install.log", python="py", run=run)
    installer._lock.acquire()
    installer.state["running"] = True
    installer._install()  # what start() runs in the background
    assert installer.state == {"running": False, "step": "model", "error": "", "done": True}
    assert (tmp_path / "dubber-omnivoice").exists()
    assert clone.TORCH_INDEX in ran[0] and clone.OMNIVOICE in ran[1] and ran[2][:2] == ["py", "-c"]

    failing = clone.Installer(tmp_path / "install.log", python="py",
                              run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1))
    (tmp_path / "dubber-omnivoice").unlink()
    assert failing.start()
    for _ in range(100):
        if not failing.state["running"]:
            break
        __import__("time").sleep(0.02)
    assert failing.state["error"] == "torch" and not failing.state["done"]
    assert not (tmp_path / "dubber-omnivoice").exists()


def test_install_progress_counts_the_bytes_downloaded(tmp_path):
    """The progress bar: PyTorch's wheel growing in pip's temp folder, then the model in the Hugging Face cache."""
    log = tmp_path / "install.log"
    installer = clone.Installer(log, python="py")
    assert installer.progress() is None  # not running
    installer.state.update(running=True, step="torch")
    log.write_text("\n== 2026-10-29 10:00:00 torch: py -m pip install ...\n"
                   "Looking in indexes: https://download.pytorch.org/whl/cu128\n"
                   "10:00:01,000   Downloading torch-2.9.0+cu128-cp312-cp312-win_amd64.whl.metadata (30 kB)\n"
                   "Downloading https://download.pytorch.org/whl/cu128/torch-2.9.0%2Bcu128-cp312-cp312-win_amd64.whl"
                   " (3400.0 MB)\n", encoding="utf-8")
    temp = tmp_path / "temp"
    (temp / "pip-unpack-abc").mkdir(parents=True)
    (temp / "pip-unpack-abc" / "torch-2.9.0+cu128-cp312-cp312-win_amd64.whl").write_bytes(b"x" * 1000)
    clone.STEP_BYTES["torch"], saved = 2000, clone.STEP_BYTES["torch"]
    try:
        assert installer.progress(temp_dir=temp) == round(clone.STEP_SHARES["torch"] * 0.5, 3)
    finally:
        clone.STEP_BYTES["torch"] = saved

    installer.state["step"] = "model"
    hub = tmp_path / "hub"
    blobs = hub / "models--k2-fsa--OmniVoice" / "blobs"
    blobs.mkdir(parents=True)
    (blobs / "abc.incomplete").write_bytes(b"x" * 10)
    before = clone.STEP_SHARES["torch"] + clone.STEP_SHARES["omnivoice"]
    assert before <= installer.progress(hub_dir=hub) < before + 0.01
    clone.STEP_BYTES["model"], saved = 10, clone.STEP_BYTES["model"]
    try:  # all bytes there, still unpacking/checking: never 100% before the install says so
        assert installer.progress(hub_dir=hub) == round(before + clone.STEP_SHARES["model"] * 0.97, 3)
    finally:
        clone.STEP_BYTES["model"] = saved


def test_cuda_check_runs_once_and_says_whether_pytorch_sees_the_card(monkeypatch):
    """Adam's RTX 5060 Ti PC (2026-10-29): a 5-minute «Оригинал» dub estimated 90 minutes with the card idle. The
    check runs a tiny computation on the card in a separate Python, once per run of the program."""
    import json as _json

    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=_json.dumps(
            {"available": True, "name": "NVIDIA GeForce RTX 5060 Ti", "torch": "2.9.0+cu128", "cuda": "12.8"}) + "\n")

    monkeypatch.setattr(clone, "installed", lambda: True)
    monkeypatch.setattr(clone, "_cuda", {})
    assert clone.cuda_status(run=run, wait=True)["name"] == "NVIDIA GeForce RTX 5060 Ti"
    assert clone.cuda_ok(run=run) and len(calls) == 1  # cached
    assert "torch" in calls[0][-1] and "cuda" in calls[0][-1]

    monkeypatch.setattr(clone, "_cuda", {})
    broken = clone.cuda_status(run=lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 1, stdout="", stderr="RuntimeError: CUDA error: no kernel image is available for execution\n"), wait=True)
    assert broken["available"] is False and "no kernel image" in broken["error"]
    assert not clone.cuda_ok()
    monkeypatch.setenv("DUBBER_CLONE_DEVICE", "cpu")  # asked for on purpose (tests, measurements)
    assert clone.cuda_ok()


def test_cuda_check_does_not_block_the_settings_page(monkeypatch):
    import threading

    release = threading.Event()

    def slow(cmd, **kwargs):
        release.wait(5)
        return subprocess.CompletedProcess(cmd, 0, stdout='{"available": true}\n')

    monkeypatch.setattr(clone, "installed", lambda: True)
    monkeypatch.setattr(clone, "_cuda", {})
    assert clone.cuda_status(run=slow) is None  # still checking
    release.set()
    for _ in range(100):
        if clone.cuda_status(run=slow) is not None:
            break
        __import__("time").sleep(0.02)
    assert clone.cuda_status(run=slow) == {"available": True}
    monkeypatch.setattr(clone, "installed", lambda: False)
    monkeypatch.setattr(clone, "_cuda", {})
    assert clone.cuda_status(run=slow, wait=True) is None  # nothing to check
