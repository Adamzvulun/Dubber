from pathlib import Path

from dubber import app
from dubber.config import Settings


def test_friendly_errors_are_russian():
    assert "скачать" in app.friendly_error(RuntimeError("DownloadError: HTTP Error 403"))
    assert "интернет" in app.friendly_error(OSError("Cannot connect to host speech.platform.bing.com"))
    assert "ffmpeg" in app.friendly_error(RuntimeError("'ffmpeg' was not found on PATH"))
    assert app.friendly_error(ValueError("boom")).startswith("Что-то пошло не так")


def test_previous_results_lists_finished_folders(tmp_path: Path):
    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out")
    assert app.previous_results(settings) == []
    done = settings.output_dir / "Lecture"
    done.mkdir(parents=True)
    (done / "Lecture (RU).mp4").write_bytes(b"x")
    (settings.output_dir / "unfinished").mkdir()
    assert app.previous_results(settings) == [("Lecture", str(done))]


def test_ui_builds(tmp_path: Path):
    ui = app.build_ui(Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "o"), runner=lambda *a, **k: None)
    assert ui is not None
