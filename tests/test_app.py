import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
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
    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out", cookies_file=tmp_path / "cookies.txt")
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
    assert one["spoken"] == [None]  # no timing.json (older dubs): the page uses the line's own times

    r = c.get("/files/abc_123/subtitles_ru.srt?download=1")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert c.get("/files/abc_123/dubbed.mp4", headers={"Range": "bytes=0-99"}).status_code == 206  # seeking works

    assert c.get("/files/abc_123/meta.json").status_code == 404  # only whitelisted files
    assert c.get("/files/..%2Fsecret/dubbed.mp4").status_code == 404
    assert c.get("/api/videos/nope").status_code == 404

    assert c.delete("/api/videos/abc_123").status_code == 200
    assert c.get("/api/videos").json() == []


def test_redub_changes_video_url_and_files_are_revalidated(tmp_path):
    # Redoing a dub with the same choices rewrites output/<id>/dubbed.mp4. The browser must not keep playing its
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


def test_two_dubs_of_one_video_are_separate_entries_with_links_to_each_other(tmp_path):
    c, settings = client(tmp_path)
    def dub(folder_name, **changes):
        folder = make_video(settings.output_dir, folder_name, "Lecture")
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8")) | changes
        (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    dub("vid--ru-aaaaaa", video_id="vid", target_lang="ru", created="2026-10-17T10:00:00")
    dub("vid--en-bbbbbb", video_id="vid", target_lang="en", created="2026-10-18T10:00:00")
    dub("other")  # dubbed before 0.4.1: folder = video id, no "video_id"

    assert [v["id"] for v in c.get("/api/videos").json()] == ["vid--en-bbbbbb", "vid--ru-aaaaaa", "other"]
    ru = c.get("/api/videos/vid--ru-aaaaaa").json()
    assert ru["target_lang"] == "ru" and ru["video"].startswith("/files/vid--ru-aaaaaa/dubbed.mp4")
    assert [(s["id"], s["target_lang"]) for s in ru["siblings"]] == [("vid--en-bbbbbb", "en")]
    legacy = c.get("/api/videos/other").json()
    assert legacy["video_id"] == "other" and legacy["siblings"] == []

    assert c.delete("/api/videos/vid--en-bbbbbb").status_code == 200
    assert c.get("/api/videos/vid--ru-aaaaaa").json()["siblings"] == []


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
    assert job["started"] >= job["created"]  # the card's clock starts when the job leaves the queue
    assert seen == {"url": "https://youtu.be/x", "voice": "ru-RU-SvetlanaNeural", "background": False}


def test_remove_voice_reaches_the_pipeline_only_with_a_background(tmp_path):
    seen = []

    def runner(url, settings, progress):
        seen.append(settings.remove_voice)
        progress("Убираю оригинальный голос", 0.8)
        return SimpleNamespace(id="vid1")

    c, _ = client(tmp_path, runner)
    for background in (True, False):
        job = c.post("/api/jobs", json={"url": "https://youtu.be/x", "background": background,
                                        "remove_voice": True}).json()
        for _ in range(100):
            job = c.get(f"/api/jobs/{job['id']}").json()
            if job["status"] == "done":
                break
            time.sleep(0.02)
        assert job["status"] == "done" and job["remove_voice"] is background
    assert seen == [True, False]  # no background = nothing to remove the voice from


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


@pytest.fixture(autouse=True)
def isolated_environ(monkeypatch):
    # Saving settings also applies them to os.environ (config.save_env); keep that inside each test.
    monkeypatch.setattr(os, "environ", dict(os.environ))


def settings_client(tmp_path, check_key=None):
    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out", env_file=tmp_path / ".env",
                        glossary_file=tmp_path / "glossary.txt", claude_key="", translator="auto")
    (tmp_path / ".env").write_text("# my settings\nDUBBER_PORT=7860\n", encoding="utf-8")
    application = app.create_app(settings, runner=lambda *a, **k: None, check_key=check_key or (lambda key: None))
    return TestClient(application), settings


def test_claude_key_is_checked_saved_masked_and_removed(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    checked = []
    c, settings = settings_client(tmp_path, check_key=checked.append)
    view = c.get("/api/settings").json()
    assert view["claude"]["key_set"] is False and view["active"] is False and view["use_claude"] is True
    assert view["claude"]["model"] == "claude-opus-5-5"
    assert [m["id"] for m in view["claude"]["models"]] == ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]

    key = "sk-ant-api03-" + "x" * 30 + "WXYZ"
    view = c.post("/api/settings/claude-key", json={"key": f"  {key} "}).json()
    assert checked == [key] and view["claude"]["key_set"] and view["claude"]["key_hint"] == "…WXYZ"
    assert view["active"] is True and key not in json.dumps(view)  # never sent back to the browser
    assert key not in c.get("/api/settings").text
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert f"ANTHROPIC_API_KEY={key}" in env and "DUBBER_PORT=7860" in env and "# my settings" in env
    assert settings.claude_key == key

    assert c.delete("/api/settings/claude-key").json()["claude"]["key_set"] is False
    assert "ANTHROPIC_API_KEY" not in (tmp_path / ".env").read_text(encoding="utf-8")
    assert settings.claude_key == ""


def test_bad_claude_key_is_refused_in_both_languages(tmp_path):
    from dubber.translate import TranslatorUnavailable

    def refuse(key):
        raise TranslatorUnavailable("nope", code="auth")

    c, settings = settings_client(tmp_path, check_key=refuse)
    r = c.post("/api/settings/claude-key", json={"key": "sk-ant-api03-" + "y" * 30})
    assert r.status_code == 422 and "Ключ не подошёл" in r.json()["detail"]["ru"]
    assert "not accepted" in r.json()["detail"]["en"] and settings.claude_key == ""
    assert c.post("/api/settings/claude-key", json={"key": "hello"}).status_code == 422  # not even key-shaped
    assert "ANTHROPIC_API_KEY" not in (tmp_path / ".env").read_text(encoding="utf-8")


def test_translation_settings_and_glossary(tmp_path):
    c, settings = settings_client(tmp_path)
    view = c.put("/api/settings", json={"use_claude": False, "model": "claude-sonnet-5-5",
                                        "glossary": "sourdough = закваска\n"}).json()
    assert view["use_claude"] is False and view["claude"]["model"] == "claude-sonnet-5-5"
    assert view["glossary"] == "sourdough = закваска" and settings.glossary() == "sourdough = закваска"
    assert settings.translator == "google" and settings.claude_model == "claude-sonnet-5-5"
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "DUBBER_TRANSLATOR=google" in env and "DUBBER_CLAUDE_MODEL=claude-sonnet-5-5" in env
    assert c.put("/api/settings", json={"model": "gpt-4"}).status_code == 422
    r = c.put("/api/settings", json={"use_claude": True, "glossary": "x" * 20_001})
    assert r.status_code == 422 and settings.translator == "google"  # nothing saved when part of it is invalid
    assert c.put("/api/settings", json={"use_claude": True}).json()["use_claude"] is True


def test_requests_from_other_websites_are_refused(tmp_path):
    c, settings = settings_client(tmp_path)
    evil = {"Origin": "https://evil.example"}
    assert c.post("/api/settings/claude-key", json={"key": "sk-ant-api03-" + "z" * 30}, headers=evil).status_code == 403
    assert c.put("/api/settings", json={"use_claude": False}, headers=evil).status_code == 403
    assert c.post("/api/jobs", json={"url": "https://youtu.be/x"}, headers=evil).status_code == 403
    assert c.get("/api/settings", headers=evil).status_code == 200  # reading is harmless (and the key isn't in it)
    own = {"Origin": "http://testserver"}
    assert c.put("/api/settings", json={"use_claude": False}, headers=own).status_code == 200
    assert settings.claude_key == ""


def test_website_files_are_always_revalidated_and_version_is_served(tmp_path):
    from dubber import __version__

    c, _ = client(tmp_path)
    for path in ("/", "/app.js", "/styles.css", "/i18n.js"):
        r = c.get(path)
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache", path
    etag = c.get("/app.js").headers["etag"]
    assert c.get("/app.js", headers={"If-None-Match": etag}).status_code == 304  # cheap when nothing changed
    assert c.get("/api/version").json() == {"version": __version__}


def test_running_job_reports_time_left(tmp_path):
    import threading

    from dubber import pipeline

    clock = SimpleNamespace(now=0.0)
    step, done = threading.Event(), threading.Event()

    def runner(url, settings, progress):
        labels = {key: label for key, label, _ in pipeline.STAGES}
        progress(labels["download"], 0.0)
        clock.now = 40.0
        progress(labels["transcribe"], 0.10)  # download (10 % by weight) took 40 s
        step.set()
        done.wait(5)
        return SimpleNamespace(id="vid1")

    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out")
    c = TestClient(app.create_app(settings, runner=runner, clock=lambda: clock.now))
    job = c.post("/api/jobs", json={"url": "https://youtu.be/x"}).json()
    assert job["eta_seconds"] is None and "_tracker" not in job
    assert step.wait(5)
    job = c.get(f"/api/jobs/{job['id']}").json()
    # Default shares: download 0.08 took 40 s → 500 s per share; 0.92 left → 460 s.
    assert job["status"] == "running" and abs(job["eta_seconds"] - 460) <= 1
    done.set()
    assert wait_for(c, job["id"], "done")["eta_seconds"] is None


def test_second_start_detects_the_program_already_running(monkeypatch, capsys):
    def answer(body):
        def fetch(host, port, timeout):
            if body is None:
                raise ConnectionRefusedError("nothing listens")
            return body
        return fetch

    monkeypatch.setattr(app, "_version_body", answer(None))
    assert app.running_version("127.0.0.1", 7860) is None
    monkeypatch.setattr(app, "_version_body", answer(b'{"detail":"Not Found"}'))
    assert app.running_version("127.0.0.1", 7860) == ""  # an old Dubber without /api/version
    monkeypatch.setattr(app, "_version_body", answer(b"<html>"))
    assert app.running_version("127.0.0.1", 7860) == ""  # some other program
    monkeypatch.setattr(app, "_version_body", answer(b'{"version": "0.3.0"}'))
    assert app.running_version("127.0.0.1", 7860) == "0.3.0"

    monkeypatch.setattr(app.webbrowser, "open", lambda url: pytest.fail("must not open the old page"))
    assert app.main() == 1
    assert "уже запущен (версия 0.3.0)" in capsys.readouterr().out


def test_version_check_against_a_real_server_port(tmp_path):
    import socket

    with socket.socket() as s:  # a free port with nothing listening
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert app.running_version("127.0.0.1", port, timeout=0.5) is None


def test_page_links_its_files_under_new_addresses_for_each_release(tmp_path):
    # Browsers keep the old styles.css / app.js on a refresh (only the page itself is re-checked) when they were
    # saved before the server sent no-cache — after an update Adam saw the new page with the old styles. Each release
    # (and each changed file) therefore gets new addresses.
    from dubber import __version__

    c, _ = client(tmp_path)
    for path in ("/", "/index.html"):
        page = c.get(path)
        assert page.status_code == 200 and page.headers["cache-control"] == "no-cache"
        assert "__ASSETS__" not in page.text
        tag = app.asset_tag()
        for name in ("styles.css", "i18n.js", "app.js"):
            assert f'"{name}?v={tag}"' in page.text  # relative: the phone app serves the same page under /p/<token>/
        assert tag.startswith(__version__)
    assert c.get(f"/app.js?v={app.asset_tag()}").status_code == 200


def test_original_voice_job_and_install(tmp_path, monkeypatch):
    from dubber import clone

    seen, started = [], []

    def runner(url, settings, progress):
        seen.append(settings.voice)
        return SimpleNamespace(id="vid1")

    class FakeInstaller:
        state = {"running": False, "step": "", "error": "", "done": False}

        def start(self):
            started.append(True)
            self.state = {**self.state, "running": True, "step": "torch"}
            return True

        def progress(self):
            return 0.25 if self.state["running"] else None

    gpu = {"gpu": {"name": "NVIDIA GeForce RTX 3070", "vram_gb": 8.0}, "gpu_ok": True, "installed": False,
           "ready": False, "min_vram_gb": 6.0, "unsupported": ["he"]}
    status = dict(gpu)
    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out")
    c = TestClient(app.create_app(settings, runner=runner, clone_status=lambda: status, installer=FakeInstaller()))

    assert c.get("/api/clone").json()["gpu"]["name"] == "NVIDIA GeForce RTX 3070"
    answer = c.post("/api/clone/install").json()
    assert started == [True] and answer["install"]["step"] == "torch" and answer["install"]["progress"] == 0.25
    status.update(gpu=None, gpu_ok=False)
    r = c.post("/api/clone/install")
    assert r.status_code == 409 and "NVIDIA" in r.json()["detail"]["ru"] and len(started) == 1

    # The voice choice reaches the pipeline as "original"; the job card shows the separation step only when used.
    monkeypatch.setattr(clone, "ready", lambda: True)
    monkeypatch.setattr(clone, "cuda_ok", lambda: True)  # PyTorch computes on the card
    for lang, separate in (("ru", True), ("he", False)):
        job = c.post("/api/jobs", json={"url": "https://youtu.be/x", "voice": "original", "lang": lang}).json()
        for _ in range(100):
            job = c.get(f"/api/jobs/{job['id']}").json()
            if job["status"] == "done":
                break
            time.sleep(0.02)
        assert job["status"] == "done" and job["separate"] is separate and job["clone"] is separate
    assert seen == ["original", "original"]
    assert c.post("/api/jobs", json={"url": "https://youtu.be/x", "voice": "robot"}).status_code == 422


def test_spoken_times_follow_the_dub_voice(tmp_path):
    timing = tmp_path / "timing.json"
    timing.write_text(json.dumps({"lines": 2, "detail": [
        {"index": 0, "start": 1.0, "delay": 0.0, "spoken": 2.5},
        {"index": 2, "start": 4.0, "delay": 0.4, "spoken": 1.25},  # started late: pushed by the line before
        {"index": 9, "start": 9.0, "delay": 0.0, "spoken": 1.0},  # not a line of this video
        {"index": 1},  # broken entry
    ]}))
    assert app.spoken_times(timing, 3) == [[1.0, 3.5], None, [4.4, 5.65]]
    timing.write_text("not json")
    assert app.spoken_times(timing, 2) == [None, None]
    assert app.spoken_times(tmp_path / "missing.json", 1) == [None]


def test_site_logins_add_merge_and_remove(tmp_path):
    c, settings = client(tmp_path)
    state = c.get("/api/cookies").json()
    assert not state["saved"] and [s["site"] for s in state["sites"]] == ["youtube", "tiktok", "instagram", "facebook"]

    insta = ".instagram.com\tTRUE\t/\tTRUE\t4000000000\tsessionid\tabc\n.bank.com\tTRUE\t/\tTRUE\t0\tx\ty\n"
    state = c.post("/api/cookies", content=insta.encode()).json()
    assert state["saved"] and {s["site"] for s in state["sites"] if s["logged_in"]} == {"instagram"}
    assert "bank.com" not in settings.cookies_file.read_text()  # other sites' cookies are never kept

    fb = "# Netscape HTTP Cookie File\n.facebook.com\tTRUE\t/\tTRUE\t4000000000\tc_user\t1\n"
    state = c.post("/api/cookies", content=fb.encode()).json()
    assert {s["site"] for s in state["sites"] if s["logged_in"]} == {"instagram", "facebook"}

    bad = c.post("/api/cookies", content=b"hello")
    assert bad.status_code == 422 and "cookies.txt" in bad.json()["detail"]["ru"]
    assert c.post("/api/cookies", content=fb.encode(), headers={"Origin": "https://evil.example"}).status_code == 403

    assert not c.delete("/api/cookies").json()["saved"]
    assert not settings.cookies_file.exists()


def test_login_and_site_errors_are_explained():
    login = RuntimeError("ERROR: [Instagram] C1x: Requested content is not available, rate-limit reached or login "
                         "required. Use --cookies-from-browser or --cookies for the authentication.")
    assert "Вход на сайты" in app.friendly_error(login)
    assert "Site logins" in app.friendly_error(login, "en")
    assert "приватное" in app.friendly_error(RuntimeError("ERROR: [TikTok] 1: This video is private"))
    limited = RuntimeError("ERROR: [Instagram] C1: The webpage request was redirected to the login page. You have "
                           "exceeded the rate-limit for accessing posts anonymously. Use --cookies")
    assert "Подождите час" in app.friendly_error(limited)
    assert "TikTok" in app.friendly_error(RuntimeError("ERROR: Unsupported URL: https://vimeo.com/1"))
