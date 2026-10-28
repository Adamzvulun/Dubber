import shutil
import subprocess
from pathlib import Path

import pytest

from dubber import media
from dubber.download import base_opts, download, is_url


def test_is_url():
    assert is_url("https://youtu.be/x") and not is_url("C:/videos/a.mp4")
    assert not is_url("https://exa mple") and not is_url("https://nodot") and not is_url("https://")
    assert is_url(" https://www.youtube.com/watch?v=E5hJF0QRPnA&pp=ugUEEgJlbg%3D%3D ")


def test_cookies_option(tmp_path, monkeypatch):
    monkeypatch.delenv("DUBBER_COOKIES", raising=False)
    assert "cookiefile" not in base_opts(tmp_path / "none.txt")
    saved = tmp_path / "saved.txt"  # the file the Settings page writes
    saved.write_text("# Netscape HTTP Cookie File\n")
    assert base_opts(saved)["cookiefile"] == str(saved)
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("DUBBER_COOKIES", str(cookies))
    assert base_opts()["cookiefile"] == str(cookies)
    monkeypatch.setenv("DUBBER_COOKIES", str(tmp_path / "missing.txt"))
    with pytest.raises(FileNotFoundError):
        base_opts()


def _clip(path, codec):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", "1", "-c:v", codec, "-c:a", "aac", str(path)],
                   check=True)
    return path


class FakeYDL:
    """yt-dlp stand-in: "downloads" a prepared clip the way yt-dlp names it (outtmpl)."""
    clip: Path
    info: dict

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        if download:
            target = Path(self.opts["outtmpl"].replace("%(ext)s", "mp4"))
            shutil.copyfile(self.clip, target)
        return self.info


@pytest.mark.parametrize("codec, reencoded", [("libx265", True), ("libx264", False)])
def test_downloaded_video_is_always_h264(tmp_path, monkeypatch, codec, reencoded):
    import yt_dlp

    FakeYDL.clip = _clip(tmp_path / f"clip-{codec}.mp4", codec)  # TikTok often serves HEVC
    FakeYDL.info = {"id": "7345", "title": "Pasta", "extractor_key": "TikTok"}
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    got = download("https://www.tiktok.com/@a/video/7345", tmp_path / "work")
    assert got.id == "tiktok-7345" and got.title == "Pasta"
    assert media.video_codec(got.path) == "h264" and media.has_audio(got.path)
    assert sorted(p.name for p in (tmp_path / "work").iterdir()) == ["source.mp4"]  # nothing left behind
    assert (media.video_codec(FakeYDL.clip) != "h264") == reencoded


def test_uploaded_hevc_file_is_converted_and_kept(tmp_path):
    original = _clip(tmp_path / "iphone.mov", "libx265")
    got = download(str(original), tmp_path / "work")
    assert media.video_codec(got.path) == "h264" and original.exists()  # the user's file is never touched
