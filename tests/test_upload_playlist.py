"""Uploading a video file from the website, and queueing a playlist (no network: yt-dlp is replaced)."""

import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from dubber import app, download
from dubber.config import Settings


def client(tmp_path, seen=None):
    def runner(url, settings, progress):
        if seen is not None:
            seen.append(url)
        return SimpleNamespace(id="vid1")

    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out")
    return TestClient(app.create_app(settings, runner=runner)), settings


def wait_done(c, job_id):
    for _ in range(100):
        job = c.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    return job


def test_upload_then_dub_the_file(tmp_path):
    seen = []
    c, settings = client(tmp_path, seen)
    r = c.post("/api/upload", params={"name": r"C:\Users\me\Видео\Лекция 1.mp4"}, content=b"video bytes")
    assert r.status_code == 200
    up = r.json()
    assert up["name"] == "Лекция 1.mp4" and up["file"].endswith("/Лекция 1.mp4")
    path = settings.work_dir / "uploads" / up["file"]
    assert path.read_bytes() == b"video bytes"
    # the same file again lands in the same place with the same time stamp → same video id → the cache is reused
    first_id = download.local_video_id(path)
    assert c.post("/api/upload", params={"name": "Лекция 1.mp4"}, content=b"video bytes").json() == up
    assert download.local_video_id(path) == first_id

    job = c.post("/api/jobs", json={"file": up["file"], "voice": "female"}).json()
    assert job["title"] == "Лекция 1.mp4" and job["file"] == up["file"]
    assert wait_done(c, job["id"])["status"] == "done"
    assert seen == [str(path)]
    assert not path.exists()  # a finished dub keeps its own copy of the video (work/<id>/source.mp4)


def test_upload_refuses_wrong_files_and_other_sites(tmp_path):
    c, _ = client(tmp_path)
    assert c.post("/api/upload", params={"name": "notes.pdf"}, content=b"x").status_code == 422
    assert c.post("/api/upload", params={"name": "empty.mp4"}, content=b"").status_code == 422
    r = c.post("/api/upload", params={"name": "a.mp4"}, content=b"x", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert c.post("/api/jobs", json={"file": "../../etc/passwd"}).status_code == 422
    assert c.post("/api/jobs", json={"file": "0123456789ab/missing.mp4"}).status_code == 422
    assert c.post("/api/jobs", json={}).status_code == 422


def test_playlist_entries_from_yt_dlp(monkeypatch):
    seen = {}

    class FakeYDL:
        def __init__(self, opts):
            seen.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"title": "Курс", "entries": [
                {"id": "aaaaaaaaaaa", "title": "Урок 1", "url": "https://www.youtube.com/watch?v=aaaaaaaaaaa"},
                {"id": "bbbbbbbbbbb", "title": None, "url": "bbbbbbbbbbb"},
                {"title": "[Private video]"},
            ]}

    import yt_dlp
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    result = download.playlist_entries("https://www.youtube.com/playlist?list=PL1")
    assert result == {"title": "Курс", "entries": [
        {"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "Урок 1"},
        {"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "title": "bbbbbbbbbbb"},
    ]}
    assert seen["extract_flat"] == "in_playlist" and seen["noplaylist"] is False and seen["playlistend"] == 200


def test_playlist_api(tmp_path, monkeypatch):
    c, _ = client(tmp_path)
    monkeypatch.setattr(download, "playlist_entries", lambda url, limit=200: {"title": "Курс", "entries": [
        {"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "Урок 1"}]})
    r = c.post("/api/playlist", json={"url": "https://www.youtube.com/playlist?list=PL1"})
    assert r.json()["entries"][0]["title"] == "Урок 1"
    assert c.post("/api/playlist", json={"url": "not a link"}).status_code == 422

    def broken(url, limit=200):
        raise RuntimeError("DownloadError: Sign in to confirm you're not a bot")

    monkeypatch.setattr(download, "playlist_entries", broken)
    r = c.post("/api/playlist", json={"url": "https://www.youtube.com/playlist?list=PL1"})
    assert r.status_code == 502 and "робот" in r.json()["detail"]["ru"]


def test_the_same_upload_dubbed_twice_keeps_the_file_until_both_are_done(tmp_path):
    # QA: dubbing one uploaded file into two languages — the first finished job deleted the file the second needed.
    import threading
    gates = {"ru": threading.Event(), "en": threading.Event()}

    def runner(url, settings, progress):
        gates[settings.target_lang].wait(5)
        return SimpleNamespace(id=f"vid-{settings.target_lang}")

    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out")
    c = TestClient(app.create_app(settings, runner=runner))
    up = c.post("/api/upload", params={"name": "a.mp4"}, content=b"video").json()
    path = settings.work_dir / "uploads" / up["file"]
    first = c.post("/api/jobs", json={"file": up["file"], "lang": "ru"}).json()
    second = c.post("/api/jobs", json={"file": up["file"], "lang": "en"}).json()
    gates["ru"].set()
    assert wait_done(c, first["id"])["status"] == "done"
    assert path.exists()  # the English dub still needs it
    gates["en"].set()
    assert wait_done(c, second["id"])["status"] == "done"
    assert not path.exists()
