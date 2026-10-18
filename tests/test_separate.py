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


def test_cancel_leaves_no_file(tmp_path):
    source = stereo_tone(tmp_path / "in.wav", 20)

    def cancel(fraction):
        if fraction > 0.3:
            raise KeyboardInterrupt  # what a cancelled job raises from its progress callback (any exception)

    with pytest.raises(KeyboardInterrupt):
        separate.separate_background(source, tmp_path / "bg.wav", model=no_voice_model([]), progress=cancel)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.wav"]
