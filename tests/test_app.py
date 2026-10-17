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
    assert "voice service" in app.friendly_error(RuntimeError("No audio was received"), "en")
    assert app.friendly_error(ValueError("boom"), "en").startswith("Something went wrong")


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
    assert videos[0]["video"].startswith("/files/abc_123/dubbed.mp4?v=")

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


def test_redub_changes_video_url_and_files_are_revalidated(tmp_path):
    # Dubbing a video into another language rewrites output/<id>/dubbed.mp4. The browser must not keep playing its
    # cached copy of the previous dub (Adam: Hebrew page, Russian voice).
    c, settings = client(tmp_path)
    folder = make_video(settings.output_dir, "abc_123", "Lecture")
    first = c.get("/api/videos/abc_123").json()["video"]
    assert first.startswith("/files/abc_123/dubbed.mp4?v=")
    assert c.get(first).headers["cache-control"] == "no-cache"  # always ask the server whether the file changed

    (folder / "dubbed.mp4").write_bytes(b"1" * 2000)  # the new dub
    second = c.get("/api/videos/abc_123").json()["video"]
    assert second != first
    assert c.get("/api/videos").json()[0]["video"] == second
    assert c.get(second).content == b"1" * 2000


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


def wait_for(c, job_id, status, tries=200):
    for _ in range(tries):
        job = c.get(f"/api/jobs/{job_id}").json()
        if job["status"] == status:
            return job
        time.sleep(0.02)
    return job


def test_cancel_running_and_queued_jobs(tmp_path):
    import threading

    started, release, ran = threading.Event(), threading.Event(), []

    def runner(url, settings, progress):
        ran.append(url)
        progress("Скачиваю видео", 0.0)
        started.set()
        release.wait(2)
        progress("Распознаю английскую речь", 0.3)  # first report after cancel → stops here
        ran.append("finished " + url)
        return SimpleNamespace(id="v")

    c, _ = client(tmp_path, runner)
    first = c.post("/api/jobs", json={"url": "https://youtu.be/a"}).json()
    second = c.post("/api/jobs", json={"url": "https://youtu.be/b"}).json()
    assert started.wait(2)

    queued = c.post(f"/api/jobs/{second['id']}/cancel").json()
    assert queued["status"] == "cancelled"
    running = c.post(f"/api/jobs/{first['id']}/cancel").json()
    assert running["status"] == "running" and running["cancel_requested"]
    release.set()

    assert wait_for(c, first["id"], "cancelled")["status"] == "cancelled"
    time.sleep(0.1)
    assert ran == ["https://youtu.be/a"]  # neither finished, the queued one never started
    assert c.post(f"/api/jobs/{first['id']}/cancel").status_code == 200  # cancelling twice is harmless
    third = c.post("/api/jobs", json={"url": "https://youtu.be/c"}).json()
    assert wait_for(c, third["id"], "done")["status"] == "done"
    assert c.post(f"/api/jobs/{third['id']}/cancel").status_code == 409  # finished work can't be cancelled
    assert c.post("/api/jobs/nope/cancel").status_code == 404


def test_languages_api_and_job_language(tmp_path):
    seen = {}

    def runner(url, settings, progress):
        seen.update(lang=settings.target_lang, voice=settings.voice)
        return SimpleNamespace(id="v")

    c, _ = client(tmp_path, runner)
    langs = {x["code"]: x for x in c.get("/api/languages").json()}
    assert len(langs) == 12 and langs["he"]["rtl"] and langs["ru"]["name_en"] == "Russian"
    assert c.post("/api/jobs", json={"url": "https://youtu.be/x", "lang": "xx"}).status_code == 422
    job = c.post("/api/jobs", json={"url": "https://youtu.be/x", "lang": "uk", "voice": "female"}).json()
    assert wait_for(c, job["id"], "done")["lang"] == "uk"
    assert seen == {"lang": "uk", "voice": "uk-UA-PolinaNeural"}


def test_new_and_legacy_video_files(tmp_path):
    c, settings = client(tmp_path)
    legacy = make_video(settings.output_dir, "old", "Old")  # dubbed before languages existed
    (legacy / "subtitles_en.srt").write_text("x", encoding="utf-8")
    assert c.get("/api/videos/old").json()["files"]["src_vtt"] == "subtitles_en.vtt"
    r = c.get("/files/old/subtitles_en.srt?download=1")
    assert r.status_code == 200 and "original" in r.headers["content-disposition"]

    new = make_video(settings.output_dir, "new", "New")
    meta = json.loads((new / "meta.json").read_text(encoding="utf-8"))
    meta.update(target_lang="he", source_lang="fr", files={"dub_vtt": "subtitles_he.vtt"})
    (new / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (new / "subtitles_he.srt").write_text("x", encoding="utf-8")
    (new / "transcript_src_he.txt").write_text("x", encoding="utf-8")
    from urllib.parse import unquote

    assert "(HE).srt" in unquote(c.get("/files/new/subtitles_he.srt?download=1").headers["content-disposition"])
    assert c.get("/files/new/transcript_src_he.txt").status_code == 200
    assert c.get("/files/new/subtitles_xx.srt").status_code == 404
    assert c.get("/files/new/segments.json").status_code == 404
