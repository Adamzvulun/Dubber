"""Disk space on the Settings page: what the cache and the library take, and clearing a video's cache."""

import json
import threading

from fastapi.testclient import TestClient

from dubber import app
from dubber.config import Settings


def setup(tmp_path, runner=None):
    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out")
    work = settings.work_dir
    (work / "vidA").mkdir(parents=True)
    (work / "vidA" / "source.mp4").write_bytes(b"x" * 3000)
    (work / "vidA" / "info.json").write_text(json.dumps({"id": "vidA", "title": "Лекция A", "channel": ""}))
    (work / "vidB" / "clips").mkdir(parents=True)
    (work / "vidB" / "clips" / "1.mp3").write_bytes(b"x" * 1000)
    (work / "uploads" / "0123456789ab").mkdir(parents=True)
    (work / "uploads" / "0123456789ab" / "a.mp4").write_bytes(b"x" * 500)
    (work / "stage_times.json").write_text("[]")  # this PC's timings: never part of "cache"
    dub = settings.output_dir / "vidB--ru-abcdef"
    dub.mkdir(parents=True)
    (dub / "dubbed.mp4").write_bytes(b"x" * 2000)
    (dub / "meta.json").write_text(json.dumps({"id": "vidB--ru-abcdef", "video_id": "vidB", "title": "Видео B",
                                               "created": "2026-10-18T10:00:00"}))
    site = app.create_app(settings, runner=runner or (lambda *a, **k: None))
    return TestClient(site), settings


def test_storage_sizes_per_video(tmp_path):
    c, _ = setup(tmp_path)
    s = c.get("/api/storage").json()
    info = len((tmp_path / "w" / "vidA" / "info.json").read_bytes())
    assert s["cache"] == 3000 + info + 1000 + 500 and s["library"] > 2000 and s["uploads"] == 500
    rows = {v["video_id"]: v for v in s["videos"]}
    assert rows["vidA"] == {"video_id": "vidA", "title": "Лекция A", "cache": 3000 + info, "library": 0, "dubs": 0}
    assert rows["vidB"]["title"] == "Видео B" and rows["vidB"]["dubs"] == 1 and rows["vidB"]["library"] > 2000
    assert [v["video_id"] for v in s["videos"]] == ["vidA", "vidB"]  # biggest cache first
    assert "uploads" not in rows


def test_clear_one_video_and_all(tmp_path):
    c, settings = setup(tmp_path)
    assert c.delete("/api/storage/cache/vidB").status_code == 200
    assert not (settings.work_dir / "vidB").exists()
    assert (settings.output_dir / "vidB--ru-abcdef" / "dubbed.mp4").exists()  # the dub stays playable
    assert c.delete("/api/storage/cache/..%2Fout").status_code in (404, 405)  # never reaches outside work/
    assert (settings.output_dir / "vidB--ru-abcdef").exists()
    assert c.delete("/api/storage/cache/stage_times.json").status_code == 404
    assert c.delete("/api/storage/cache").json()["freed"] > 3000
    assert sorted(p.name for p in settings.work_dir.iterdir()) == ["stage_times.json"]
    assert c.get("/api/storage").json()["cache"] == 0


def test_clearing_waits_for_running_dubs(tmp_path):
    release = threading.Event()
    c, _ = setup(tmp_path, runner=lambda *a, **k: release.wait(5))
    c.post("/api/jobs", json={"url": "https://youtu.be/x"})
    try:
        r = c.delete("/api/storage/cache/vidA")
        assert r.status_code == 409 and "озвучк" in r.json()["detail"]["ru"]
        assert c.delete("/api/storage/cache").status_code == 409
    finally:
        release.set()
