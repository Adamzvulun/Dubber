import os

from dubber import config


def test_ffmpeg_in_the_program_folder_goes_on_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    config.use_local_ffmpeg(tmp_path)  # no ffmpeg folder: PATH unchanged
    assert os.environ["PATH"] == "/usr/bin"
    local = tmp_path / "ffmpeg" / "bin"
    local.mkdir(parents=True)
    config.use_local_ffmpeg(tmp_path)
    config.use_local_ffmpeg(tmp_path)  # not added twice
    assert os.environ["PATH"].split(os.pathsep) == [str(local), "/usr/bin"]
