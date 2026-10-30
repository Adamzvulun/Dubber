"""Removing the original voice (separate.py) with a stand-in model; the real ONNX model is checked by hand (STATUS)."""

import numpy as np
import pytest

from dubber import separate
from dubber.media import decode_audio, run_ffmpeg


def stereo_tone(path, seconds):
    run_ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}", "-f", "lavfi", "-i",
                f"sine=frequency=330:duration={seconds}", "-filter_complex", "[0:a][1:a]amerge=inputs=2",
                "-ar", "44100", str(path)])
    return path


def no_voice_model(calls):
    """Everything is "drums" (no vocals): the background must come back equal to the input."""
    def model(chunk):
        calls.append(chunk.shape)
        stems = np.zeros((1, 4, *chunk.shape[1:]), dtype=np.float32)
        stems[0, 0] = chunk[0]
        return stems
    return model


def test_background_is_rebuilt_across_windows(tmp_path):
    source = stereo_tone(tmp_path / "in.wav", 20)  # 20 s = 4 overlapping 7.8-s windows
    calls, seen = [], []
    out = separate.separate_background(source, tmp_path / "bg.wav", model=no_voice_model(calls), progress=seen.append)
    assert all(shape == (1, 2, separate.WINDOW) for shape in calls) and len(calls) == 4
    assert seen == sorted(seen) and seen[-1] == 1.0
    original, background = decode_audio(source, 44100), decode_audio(out, 44100)
    assert abs(len(background) - len(original)) < 10
    assert float(np.abs(background[: len(original)] - original[: len(background)]).max()) < 2e-3  # 16-bit WAV

    # A finished file is reused: the model is not needed again.
    assert separate.separate_background(source, out, model=lambda chunk: pytest.fail("model called")) == out


def test_voice_is_removed(tmp_path):
    source = stereo_tone(tmp_path / "in.wav", 3)

    def all_voice(chunk):
        stems = np.zeros((1, 4, *chunk.shape[1:]), dtype=np.float32)
        stems[0, separate.VOCALS] = chunk[0]
        return stems

    out = separate.separate_background(source, tmp_path / "bg.wav", model=all_voice)
    assert float(np.abs(decode_audio(out, 44100)).max()) < 1e-3


def test_vocals_are_saved_too(tmp_path):
    source = stereo_tone(tmp_path / "in.wav", 3)

    def all_voice(chunk):
        stems = np.zeros((1, 4, *chunk.shape[1:]), dtype=np.float32)
        stems[0, separate.VOCALS] = chunk[0]
        return stems

    bg, vocals = tmp_path / "bg.wav", tmp_path / "vocals.wav"
    separate.separate_background(source, bg, model=all_voice, vocals_wav=vocals)
    original, voice = decode_audio(source, 44100), decode_audio(vocals, 44100)
    assert float(np.abs(voice[: len(original)] - original[: len(voice)]).max()) < 2e-3

    # Both files exist: reused. A background without vocals (made before the voice was needed) is made again.
    assert separate.separate_background(source, bg, model=lambda c: pytest.fail("model called"), vocals_wav=vocals)
    vocals.unlink()
    separate.separate_background(source, bg, model=all_voice, vocals_wav=vocals)
    assert vocals.exists()


def test_cancel_leaves_no_file(tmp_path):
    source = stereo_tone(tmp_path / "in.wav", 20)

    def cancel(fraction):
        if fraction > 0.3:
            raise KeyboardInterrupt  # what a cancelled job raises from its progress callback (any exception)

    with pytest.raises(KeyboardInterrupt):
        separate.separate_background(source, tmp_path / "bg.wav", model=no_voice_model([]), progress=cancel)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.wav"]


FAKE_ORT = '''
import numpy as np
class SessionOptions:
    graph_optimization_level = None
class GraphOptimizationLevel:
    ORT_ENABLE_ALL = 99
class InferenceSession:
    """onnxruntime-gpu stand-in: "{providers}" is what the card offers; everything is "drums", nothing "vocals"."""
    def __init__(self, path, sess_options=None, providers=()):
        self.providers = {providers!r}
    def get_providers(self):
        return self.providers
    def run(self, names, feeds):
        mix = feeds["mix"]
        stems = np.zeros((1, 4, *mix.shape[1:]), dtype=np.float32)
        stems[0, 0] = mix[0]
        return [stems]
'''


def fake_ort_dir(tmp_path, providers):
    """A folder like gpu.ORT_DIR whose `onnxruntime` is a stand-in, and whose `huggingface_hub` (first on the child's
    path too) skips the model download."""
    ort = tmp_path / "ort-gpu"
    (ort / "onnxruntime" / "capi").mkdir(parents=True)
    (ort / "onnxruntime" / "__init__.py").write_text(FAKE_ORT.format(providers=providers), encoding="utf-8")
    (ort / "huggingface_hub").mkdir()
    (ort / "huggingface_hub" / "__init__.py").write_text("def hf_hub_download(*a, **k):\n    return 'model.onnx'\n")
    return ort


def test_voice_removal_runs_on_the_card_in_a_child_process(tmp_path, monkeypatch, capsys):
    """ADR-045: onnxruntime-gpu lives in its own folder; a child process loads it first and does the work there."""
    source = stereo_tone(tmp_path / "in.wav", 10)
    ort = fake_ort_dir(tmp_path, ["CUDAExecutionProvider", "CPUExecutionProvider"])
    monkeypatch.setattr(separate.gpu, "ORT_DIR", ort)
    monkeypatch.setattr(separate, "_gpu_failed", False)
    monkeypatch.setattr(separate, "load_model", lambda card=False: pytest.fail("the processor was used"))
    monkeypatch.delenv("DUBBER_DEVICE", raising=False)
    seen = []
    out = separate.separate_background(source, tmp_path / "w" / "bg.wav", progress=seen.append,
                                       vocals_wav=tmp_path / "w" / "vocals.wav")
    assert "видеокарте" in capsys.readouterr().out
    assert seen[-1] == 1.0 and seen == sorted(seen)
    original, background = decode_audio(source, 44100), decode_audio(out, 44100)
    assert float(np.abs(background[: len(original)] - original[: len(background)]).max()) < 2e-3
    assert (tmp_path / "w" / "vocals.wav").exists()


def test_when_the_card_is_not_used_the_processor_does_it(tmp_path, monkeypatch, capsys):
    source = stereo_tone(tmp_path / "in.wav", 5)
    monkeypatch.setattr(separate.gpu, "ORT_DIR", fake_ort_dir(tmp_path, ["CPUExecutionProvider"]))  # CUDA missing
    monkeypatch.setattr(separate, "_gpu_failed", False)
    calls = []
    monkeypatch.setattr(separate, "load_model", lambda card=False: no_voice_model(calls))
    monkeypatch.delenv("DUBBER_DEVICE", raising=False)
    out = separate.separate_background(source, tmp_path / "w" / "bg.wav")
    assert out.exists() and calls and "процессоре" in capsys.readouterr().out
    assert separate._gpu_failed  # not tried again in this run of the program
    assert not list((tmp_path / "w").glob("tmp*"))


def test_cancelling_stops_the_child_and_leaves_nothing(tmp_path, monkeypatch):
    source = stereo_tone(tmp_path / "in.wav", 30)
    monkeypatch.setattr(separate.gpu, "ORT_DIR", fake_ort_dir(tmp_path, ["CUDAExecutionProvider"]))
    monkeypatch.setattr(separate, "_gpu_failed", False)
    monkeypatch.delenv("DUBBER_DEVICE", raising=False)

    def cancel(fraction):
        raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        separate.separate_background(source, tmp_path / "w" / "bg.wav", progress=cancel)
    assert not (tmp_path / "w" / "bg.wav").exists() and not list((tmp_path / "w").glob("tmp*"))
