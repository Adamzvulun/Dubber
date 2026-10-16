import subprocess
from pathlib import Path

import pytest


def make_tone(path: Path, seconds: float, freq: int = 440) -> Path:
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
         str(path)],
        check=True,
    )
    return path


@pytest.fixture
def tone():
    return make_tone


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    """A 6-second 320x240 H.264 video with a stereo AAC tone track."""
    out = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=6",
         "-f", "lavfi", "-i", "sine=frequency=300:duration=6",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-shortest", str(out)],
        check=True,
    )
    return out
