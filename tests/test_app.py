import json
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from dubber import app
from dubber.config import Settings


def test_friendly_errors_are_russian():
    assert "скачать" in app.friendly_error(RuntimeError("DownloadError: HTTP Error 403"))
    assert "робот" in app.friendly_error(RuntimeError("Sign in to confirm you're not a bot"))
    assert "интернет" in app.friendly_error(OSError("Cannot connect to host speech.platform.bing.com"))
    assert app.friendly_error(ValueError("boom")).startswith("Что-то пошло не так")
    hf = RuntimeError("Task error: File reconstruction error: CAS Client Error: Request middleware error: "
                      "error sending request for url (https://us.aws.cdn.hf.co/xorbs/default/0a6b)")
    assert "модель распознавания" in app.friendly_error(hf)
    assert "озвучки" in app.friendly_error(RuntimeError("Edge TTS: No audio was received for many lines"))


def make_video(output: Path, vid: str, title: str) -> Path:
    folder = output / vid
    folder.mkdir(parents=True)
    (folder / "dubbed.mp4").write_bytes(b"0" * 1000)
    (folder / "thumbnail.jpg").write_bytes(b"jpg")
    (folder / "subtitles_ru.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nПривет\n", encoding="utf-8")
    (folder / "segments.json").write_text(json.dumps([{"start": 0, "end": 1, "text": "Hi", "ru": "Привет"}]))
    meta = {"id": vid, "title": title, "duration": 60, "created": "2026-10-16T10:00:00", "voice": "ru-RU-DmitryNeural"}
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return folder


def client(tmp_path, runner=None):
    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out")
    return TestClient(app.create_app(settings, runner=runner or (lambda *a, **k: None))), settings


def test_library_watch_files_and_delete(tmp_path):
    c, settings = client(tmp_path)
    make_video(settings.output_dir, "abc_123", "Лекция: часть 1")
    (settings.output_dir / "unfinished").mkdir()  # no meta/video → not listed

    videos = c.get("/api/videos").json()
    assert [v["id"] for v in videos] == ["abc_123"]
    assert videos[0]["video"] == "/files/abc_123/dubbed.mp4"

    one = c.get("/api/videos/abc_123").json()
    assert one["segments"][0]["ru"] == "Привет"

    r = c.get("/files/abc_123/subtitles_ru.srt?download=1")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert c.get("/files/abc_123/dubbed.mp4", headers={"Range": "bytes=0-99"}).status_code == 206  # seeking works

    assert c.get("/files/abc_123/meta.json").status_code == 404  # only whitelisted files
    assert c.get("/files/..%2Fsecret/dubbed.mp4").status_code == 404
    assert c.get("/api/videos/nope").status_code == 404

    assert c.delete("/api/videos/abc_123").status_code == 200
    assert c.get("/api/videos").json() == []


def test_job_runs_with_chosen_voice_and_background(tmp_path):
    seen = {}

    def runner(url, settings, progress):
        seen.update(url=url, voice=settings.voice, background=settings.keep_background)
        progress("Перевожу на русский", 0.5)
        return SimpleNamespace(id="vid1")

    c, _ = client(tmp_path, runner)
    assert c.post("/api/jobs", json={"url": "notaurl"}).status_code == 422
    job = c.post("/api/jobs", json={"url": "https://youtu.be/x", "voice": "female", "background": False}).json()
    for _ in range(100):
        job = c.get(f"/api/jobs/{job['id']}").json()
        if job["status"] == "done":
            break
        time.sleep(0.02)
    assert job["status"] == "done" and job["video_id"] == "vid1"
    assert seen == {"url": "https://youtu.be/x", "voice": "ru-RU-SvetlanaNeural", "background": False}


def test_job_error_is_reported_in_russian(tmp_path):
    def runner(url, settings, progress):
        raise RuntimeError("DownloadError: HTTP Error 403")

    c, _ = client(tmp_path, runner)
    job = c.post("/api/jobs", json={"url": "https://youtu.be/x"}).json()
    for _ in range(100):
        job = c.get(f"/api/jobs/{job['id']}").json()
        if job["status"] == "error":
            break
        time.sleep(0.02)
    assert job["status"] == "error" and "скачать" in job["error"]


def test_home_page_is_served(tmp_path):
    c, _ = client(tmp_path)
    page = c.get("/")
    assert page.status_code == 200 and "Дубляж" in page.text
    assert c.get("/app.js").status_code == 200 and c.get("/styles.css").status_code == 200
