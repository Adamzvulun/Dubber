"""The Dubber website: a small FastAPI server + a hand-built front-end in dubber/web/.

Run: `python -m dubber.app` → opens http://127.0.0.1:7860

API
- POST /api/jobs {url | file, voice: "male"|"female", background: bool, lang, remove_voice: bool} → start dubbing
  (jobs run one after another); remove_voice keeps the music under the dub but not the speaker's voice
- POST /api/upload?name=<file name> (body: the file) → {file, name}: a video from this computer, for /api/jobs
- POST /api/playlist {url}                                           → {title, entries: [{url, title}]} (no download)
- GET  /api/languages                                              → dub languages (code, names, voices)
- GET  /api/jobs, /api/jobs/{id}                                   → progress, elapsed, rough time left (eta.py)
- GET  /api/version                                                 → {"version"} (shown in the page footer)
- POST /api/jobs/{id}/cancel                                        → stop a queued or running job
- GET  /api/videos, /api/videos/{id}                                → library, one video + its timed transcript
- DELETE /api/videos/{id}                                           → remove from the library
- GET  /files/{id}/{name}[?download=1]                               → video, subtitles, transcripts, thumbnail
- GET  /api/settings, PUT /api/settings {use_claude, model, glossary} → translation settings (saved in .env)
- POST /api/settings/claude-key {key}, DELETE /api/settings/claude-key → check + save / remove the Claude API key
- GET  /api/storage, DELETE /api/storage/cache[/{video_id}]        → disk space; clear a video's (or all) cache
- GET  /api/changelog                                               → [{version, ru, en}] newest first ("What's new")
- GET  /api/update                                                  → {current, latest, available, enabled}
- POST /api/update                                                  → install the newest `main` and restart (update.py)

Requests that change something are refused when they come from another website (Origin check): the server listens
on this computer only, but a page open in the same browser could otherwise send them.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, download, eta, languages, pipeline, translate, update
from .config import Settings, load_settings, save_env
from .download import is_url

WEB_DIR = Path(__file__).parent / "web"
STAGE_KEYS = {label: key for key, label, _ in pipeline.STAGES}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Uploaded videos: work/uploads/<first 12 hex of the file's sha1>/<file name>
_UPLOAD = re.compile(r"^[0-9a-f]{12}/[^/\\:*?\"<>|]{1,120}$")
UPLOAD_TYPES = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".3gp"}
UPLOAD_MTIME = 1_000_000_000  # every upload gets this time stamp: the same file again → the same video id → cache


def safe_file_name(name: str) -> str:
    """The file name alone (no folders), without characters Windows forbids, at most 120 characters."""
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "", name.replace("\\", "/").rsplit("/", 1)[-1]).strip().strip(".")
    if len(name) > 120:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 119 - len(ext)] + dot + ext) if dot else name[:120]
    return name

# Files the browser may fetch from output/<id>/ (see subtitles.file_names; "en"/"en_ru" names are from videos
# dubbed before other languages existed, when the original was always English and the dub Russian).
_LANG = "|".join(sorted(languages.LANGUAGES))
_SUBTITLES = re.compile(rf"^subtitles_(src|{_LANG})\.(vtt|srt)$")
_TRANSCRIPT = re.compile(rf"^transcript_(?:(src|en)_)?({_LANG})\.txt$")
_TEXT = "text/plain; charset=utf-8"
LEGACY_FILES = {
    "dub_srt": "subtitles_ru.srt", "dub_vtt": "subtitles_ru.vtt", "src_srt": "subtitles_en.srt",
    "src_vtt": "subtitles_en.vtt", "transcript": "transcript_ru.txt", "bilingual": "transcript_en_ru.txt",
}


def file_info(name: str, target: str) -> tuple[str, str | None] | None:
    """(media type, download-name template) for a file the browser may fetch, or None if not allowed."""
    tag = target.upper()
    if name == "dubbed.mp4":
        return "video/mp4", f"{{title}} ({tag}).mp4"
    if name == "thumbnail.jpg":
        return "image/jpeg", None
    if m := _SUBTITLES.match(name):
        lang, ext = m.groups()
        if ext == "vtt":
            return "text/vtt", None
        legacy_original = lang == "en" and target == "ru"  # old videos: subtitles_en = the English original
        label = "original" if lang == "src" or legacy_original else lang.upper()
        return "application/x-subrip", f"{{title}} ({label}).srt"
    if m := _TRANSCRIPT.match(name):  # same "(…)" pattern as the video and subtitles
        bilingual, lang = m.groups()
        return _TEXT, (f"{{title}} (original + {lang.upper()}).txt" if bilingual else f"{{title}} ({lang.upper()}).txt")
    return None


# (words that identify the error, Russian message, English message) — checked in order.
_ERRORS: list[tuple[Callable[[str], bool], str, str]] = [
    (lambda t: "ffmpeg" in t and "not found" in t,
     "Не найдена программа ffmpeg. Запустите установку ещё раз (install_windows.bat).",
     "ffmpeg was not found. Run the installer again (install_windows.bat)."),
    (lambda t: "not a bot" in t or "sign in to confirm" in t,
     "YouTube попросил подтвердить, что вы не робот. Попробуйте позже или настройте файл cookies (см. инструкцию).",
     "YouTube asked to confirm you're not a robot. Try again later or set up a cookies file (see the guide)."),
    (lambda t: any(w in t for w in ("huggingface", "hf.co", "cas client", "xet")),
     "Не удалось скачать модель распознавания речи (она скачивается один раз, около 500 МБ). Проверьте интернет "
     "и попробуйте снова. Если ошибка повторяется — возможно, антивирус или сеть блокируют сайт huggingface.co.",
     "Couldn't download the speech-recognition model (a one-time ~500 MB download). Check your internet and try "
     "again. If it keeps failing, an antivirus or the network may be blocking huggingface.co."),
    (lambda t: "no audio was received" in t,
     "Сервис озвучки Microsoft сейчас не отвечает. Подождите несколько минут и нажмите «Попробовать снова» — "
     "уже готовые части сохранятся.",
     "Microsoft's voice service isn't responding right now. Wait a few minutes and press “Try again” — "
     "the finished parts are kept."),
    (lambda t: "downloaderror" in t or "youtube" in t or "unsupported url" in t,
     "Не удалось скачать видео. Проверьте, что ссылка правильная и интернет работает. "
     "Если ошибка повторяется — запустите установку ещё раз, она обновит загрузчик.",
     "Couldn't download the video. Check that the link is right and the internet works. "
     "If it keeps failing, run the installer again — it updates the downloader."),
    (lambda t: "no speech found" in t,
     "В этом видео не найдено речи.",
     "No speech was found in this video."),
    (lambda t: "could not translate" in t,
     "Часть фраз не удалось перевести (ни Google, ни резервным переводчиком). Попробуйте ещё раз позже.",
     "Some lines could not be translated (neither by Google nor by the offline backup). Please try again later."),
    (lambda t: "offline translator only" in t or ("google" in t and "translat" in t),
     "Не удалось перевести: сервис Google Translate недоступен. Без него можно переводить только "
     "с английского на русский. Попробуйте позже.",
     "Couldn't translate: Google Translate is unavailable. Without it only English→Russian works. "
     "Try again later."),
    (lambda t: any(w in t for w in ("connect", "timeout", "network", "dns", "proxy", "ssl")),
     "Нет связи с интернет-сервисом перевода или озвучки. Проверьте интернет и попробуйте снова.",
     "Can't reach the translation or voice service. Check your internet and try again."),
]


def _detail(ru: str, en: str) -> dict:
    """HTTP error detail in both interface languages (the website picks one)."""
    return {"ru": ru, "en": en}


def friendly_error(exc: Exception, lang: str = "ru") -> str:
    """Turn a technical error into a short explanation with what to do (Russian or English UI)."""
    text = f"{type(exc).__name__}: {exc}".lower()
    for matches, ru, en in _ERRORS:
        if matches(text):
            return en if lang == "en" else ru
    if lang == "en":
        return f"Something went wrong. Please try again. Details for support: {exc}"
    return f"Что-то пошло не так. Попробуйте ещё раз. Подробности для помощника: {exc}"


@dataclass
class Job:
    id: str
    url: str
    voice: str  # "male" | "female"
    background: bool
    lang: str = languages.DEFAULT  # dub language
    remove_voice: bool = False  # keep music and sounds, remove the speaker's voice (Demucs)
    status: str = "queued"  # queued | running | done | error | cancelled
    stage: str = ""
    label: str = "В очереди"
    progress: float = 0.0
    error: str = ""  # Russian
    error_en: str = ""
    video_id: str = ""
    title: str = ""  # shown on the job card instead of the link (an uploaded file's name)
    file: str = ""  # an uploaded file (work/uploads/<file>), for "try again"
    created: float = field(default_factory=time.time)
    started: float = 0.0  # when it left the queue (the job card's clock starts here)
    cancel_requested: bool = False
    _tracker: eta.Tracker | None = field(default=None, repr=False)  # stage timings → time left
    _shares: dict = field(default_factory=dict, repr=False)

    def public(self) -> dict:
        out = {f.name: getattr(self, f.name) for f in dataclasses.fields(self) if not f.name.startswith("_")}
        running = self.status == "running" and self._tracker is not None
        left = self._tracker.eta(self._shares) if running else None
        out["eta_seconds"] = round(left) if left is not None else None
        return out


class JobCancelled(Exception):
    """Raised from the progress callback to stop a job the user cancelled."""


class JobRunner:
    """Runs dubbing jobs one after another in a background thread."""

    def __init__(self, settings: Settings, runner=pipeline.run, clock: Callable[[], float] = time.monotonic):
        self.settings = settings
        self.runner = runner
        self.clock = clock
        self.history = settings.work_dir / "stage_times.json"  # stage timings of finished dubs on this PC
        self.jobs: dict[str, Job] = {}
        self._queue: queue.Queue[Job] = queue.Queue()
        threading.Thread(target=self._work, daemon=True).start()

    def submit(
        self, url: str, voice: str, background: bool, lang: str = languages.DEFAULT, remove_voice: bool = False,
        title: str = "", file: str = "",
    ) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], url=url, voice=voice, background=background, lang=lang,
                  remove_voice=remove_voice and background, title=title, file=file)
        self.jobs[job.id] = job
        self._queue.put(job)
        return job

    def cancel(self, job_id: str) -> Job | None:
        """Stop a job: a queued one never starts; a running one stops at its next progress report.

        Work already done stays in work/<id>/, so starting the same video again resumes from there.
        """
        job = self.jobs.get(job_id)
        if job is None or job.status not in ("queued", "running"):
            return job
        job.cancel_requested = True
        if job.status == "queued":
            job.status, job.label = "cancelled", "Отменено"
        else:
            job.label = "Останавливаю"
        return job

    def _work(self) -> None:
        while True:
            job = self._queue.get()
            if job.status == "cancelled":
                continue
            job.status, job.label, job.started = "running", "Начинаю", time.time()
            job._tracker = eta.Tracker(
                [(key, weight) for key, _, weight in pipeline.stages(job.remove_voice)], self.clock)
            job._shares = eta.load_shares(self.history)
            settings = dataclasses.replace(
                self.settings, target_lang=job.lang, voice=languages.voice_for(job.lang, job.voice),
                keep_background=job.background, remove_voice=job.remove_voice,
            )

            def progress(label: str, fraction: float, job: Job = job) -> None:
                # Called at the start of every stage and often inside long ones (download, Whisper, TTS).
                if job.cancel_requested:
                    raise JobCancelled()
                job.stage, job.label, job.progress = STAGE_KEYS.get(label, ""), label, round(fraction, 4)
                job._tracker.update(job.stage, fraction)

            try:
                result = self.runner(job.url, settings, progress=progress)
                job.video_id, job.status, job.progress, job.label = result.id, "done", 1.0, "Готово"
                others = any(j is not job and j.file == job.file and j.status in ("queued", "running")
                             for j in list(self.jobs.values()))
                if job.file and not others:  # the dub has its own copy (work/<id>/source.mp4); a failed one keeps it
                    uploaded = Path(job.url)
                    uploaded.unlink(missing_ok=True)
                    with contextlib.suppress(OSError):
                        uploaded.parent.rmdir()
                eta.record(self.history, job._tracker.stage_seconds())
            except Exception as exc:  # shown to the user in Russian
                if job.cancel_requested:  # yt-dlp may wrap our JobCancelled in its own error
                    job.status, job.label = "cancelled", "Отменено"
                    continue
                traceback.print_exc()
                job.status, job.error, job.error_en = "error", friendly_error(exc), friendly_error(exc, "en")


class SettingsUpdate(BaseModel):
    use_claude: bool | None = None
    model: str | None = None
    glossary: str | None = None


class KeyRequest(BaseModel):
    key: str


# Rough cost of translating 10 minutes of speech (~1,500 words): ~3k input and ~4k output tokens (thinking included).
_TEN_MIN_TOKENS = (3_000, 4_000)
_KEY_ERRORS = {
    "auth": ("Ключ не подошёл. Проверьте, что он скопирован полностью.",
             "The key was not accepted. Check that it was copied completely."),
    "permission": ("У этого ключа нет доступа к Claude. Создайте новый ключ в консоли Anthropic.",
                   "This key has no access to Claude. Create a new key in the Anthropic console."),
    "unavailable": ("Не удалось связаться с Anthropic. Проверьте интернет и попробуйте снова.",
                    "Couldn't reach Anthropic. Check the internet and try again."),
}


def _key_hint(key: str) -> str:
    return f"…{key[-4:]}" if key else ""


class PlaylistRequest(BaseModel):
    url: str


class JobRequest(BaseModel):
    url: str = ""
    file: str = ""  # instead of url: an uploaded video (from POST /api/upload)
    voice: str = "male"
    background: bool = True
    lang: str = languages.DEFAULT
    remove_voice: bool = False


def _read_meta(folder: Path) -> dict | None:
    try:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (folder / "dubbed.mp4").exists():
        return None
    meta["id"] = folder.name
    meta.setdefault("video_id", folder.name)  # dubbed before 0.4.1: one folder per video, named after it
    meta["thumbnail"] = f"/files/{folder.name}/thumbnail.jpg"
    # The file name stays the same when a dub is redone with the same choices: a version in the URL stops the
    # browser from playing its cached copy of the previous one.
    video = (folder / "dubbed.mp4").stat()
    meta["video"] = f"/files/{folder.name}/dubbed.mp4?v={video.st_mtime_ns:x}{video.st_size:x}"
    if "target_lang" not in meta:  # dubbed before other languages existed: English → Russian, old file names
        meta.update(target_lang="ru", source_lang="en", files=LEGACY_FILES)
    return meta


def _save_chunk(out, digest, chunk: bytes) -> None:
    digest.update(chunk)
    out.write(chunk)


def folder_size(path: Path) -> int:
    """Bytes in a folder (0 if it doesn't exist); files that vanish meanwhile are skipped."""
    total = 0
    for item in path.rglob("*") if path.is_dir() else ():
        with contextlib.suppress(OSError):
            if item.is_file():
                total += item.stat().st_size
    return total


def models_size() -> int:
    """The speech-recognition / translation models downloaded from Hugging Face (shared by all videos)."""
    try:
        from huggingface_hub import constants

        return folder_size(Path(constants.HF_HUB_CACHE))
    except Exception:
        return 0


def asset_tag() -> str:
    """Part of the address of the site's files: changes with every release and whenever a file changes.

    A browser that saved styles.css / app.js before the server said no-cache keeps using them on a refresh (only the
    page itself is re-checked): after an update Adam saw the new page with the old styles. New addresses can't hit
    those old copies.
    """
    newest = max(f.stat().st_mtime_ns for f in WEB_DIR.iterdir() if f.is_file())
    return f"{__version__}.{newest // 1_000_000_000:x}"


class _FreshStaticFiles(StaticFiles):
    """The website's own files, always checked with the server (ETag) so an update is never hidden behind the
    browser's saved copy of the old page."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app(
    settings: Settings | None = None,
    runner=pipeline.run,
    check_key: Callable[[str], None] = translate.check_claude_key,
    clock: Callable[[], float] = time.monotonic,
    updater: update.Updater | None = None,
    restart: Callable[[], None] | None = None,
) -> FastAPI:
    """`restart` (given by main()) stops this server so main() can start the version an update installed."""
    settings = settings or load_settings()
    jobs = JobRunner(settings, runner, clock)
    updater = updater or update.Updater()
    newest: dict = {"version": None, "checked": None}  # GitHub is asked at most once an hour
    updating = threading.Lock()  # one update at a time; no new dub starts while one is installed
    app = FastAPI(title="Дубляж", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def same_origin_only(request: Request, call_next):
        # Browsers send Origin with every cross-site POST/PUT/DELETE; ours come from this very server.
        origin = request.headers.get("origin")
        if (request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api/")
                and origin is not None and urlsplit(origin).netloc != request.headers.get("host")):
            return JSONResponse({"detail": _detail("Запрос отклонён.", "Request refused.")}, status_code=403)
        return await call_next(request)

    def folder_for(video_id: str) -> Path:
        if not _ID.match(video_id):
            raise HTTPException(404)
        folder = settings.output_dir / video_id
        if not folder.is_dir():
            raise HTTPException(404)
        return folder

    @app.post("/api/jobs")
    def start_job(req: JobRequest) -> dict:
        url, title = req.url.strip(), ""
        if req.file:
            uploaded = settings.work_dir / "uploads" / req.file
            if not _UPLOAD.match(req.file) or not uploaded.is_file():
                raise HTTPException(422, _detail("Файл не найден. Выберите его ещё раз.",
                                                 "The file was not found. Choose it again."))
            url, title = str(uploaded), req.file.split("/", 1)[1]
        elif not is_url(url):
            raise HTTPException(422, _detail("Вставьте ссылку на видео — она начинается с https://",
                                             "Paste a video link — it starts with https://"))
        if req.voice not in ("male", "female"):
            raise HTTPException(422, _detail("Неизвестный голос", "Unknown voice"))
        if req.lang not in languages.LANGUAGES:
            raise HTTPException(422, _detail("Неизвестный язык", "Unknown language"))
        if updating.locked():
            raise HTTPException(409, _detail("Программа обновляется. Начните озвучку после перезапуска.",
                                             "The program is updating. Start the dub after it restarts."))
        return jobs.submit(url, req.voice, req.background, req.lang, req.remove_voice, title, req.file).public()

    @app.post("/api/upload")
    async def upload_file(request: Request, name: str) -> dict:
        clean = safe_file_name(name)
        if Path(clean).suffix.lower() not in UPLOAD_TYPES:
            raise HTTPException(422, _detail(
                "Этот файл не подходит. Нужно видео: MP4, MKV, WEBM, MOV, AVI и подобные.",
                "This file won't work. It needs to be a video: MP4, MKV, WEBM, MOV, AVI and the like."))
        uploads = settings.work_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        incoming = uploads / f".incoming-{uuid.uuid4().hex}"
        digest, size = hashlib.sha1(), 0
        try:
            with incoming.open("wb") as out:
                async for chunk in request.stream():  # in pieces: a video can be several GB
                    await asyncio.to_thread(_save_chunk, out, digest, chunk)  # pages keep answering meanwhile
                    size += len(chunk)
            if not size:
                raise HTTPException(422, _detail("Файл пустой.", "The file is empty."))
            token = f"{digest.hexdigest()[:12]}/{clean}"
            target = uploads / token
            target.parent.mkdir(exist_ok=True)
            os.replace(incoming, target)
            os.utime(target, (UPLOAD_MTIME, UPLOAD_MTIME))
        except OSError as exc:  # e.g. the disk is full
            raise HTTPException(507, _detail("Не удалось сохранить файл: на диске не хватает места?",
                                             "Couldn't save the file: is the disk full?")) from exc
        finally:
            incoming.unlink(missing_ok=True)
        return {"file": token, "name": clean}

    @app.post("/api/playlist")
    def playlist(req: PlaylistRequest) -> dict:
        if not is_url(req.url.strip()):
            raise HTTPException(422, _detail("Вставьте ссылку на плейлист.", "Paste a playlist link."))
        try:
            return download.playlist_entries(req.url.strip())
        except Exception as exc:  # shown to the user, like a failed job
            raise HTTPException(502, _detail(friendly_error(exc), friendly_error(exc, "en"))) from exc

    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    def index() -> HTMLResponse:
        page = (WEB_DIR / "index.html").read_text(encoding="utf-8").replace("__ASSETS__", asset_tag())
        return HTMLResponse(page, headers={"Cache-Control": "no-cache"})

    @app.get("/api/version")
    def version() -> dict:
        return {"version": __version__}

    def update_state() -> dict:
        enabled = updater.enabled()
        if enabled and (newest["checked"] is None or clock() - newest["checked"] > 3600):
            newest.update(version=updater.latest(), checked=clock())
        latest = newest["version"]
        return {"current": __version__, "latest": latest, "enabled": enabled,
                "available": enabled and update.is_newer(latest, __version__)}

    @app.get("/api/update")
    def get_update() -> dict:
        return update_state()

    @app.post("/api/update")
    def install_update() -> dict:
        if not updating.acquire(blocking=False):
            raise HTTPException(409, _detail("Обновление уже идёт.", "The update is already running."))
        try:
            if not update_state()["available"]:
                raise HTTPException(409, _detail("Новой версии нет.", "There is no new version."))
            if any(j.status in ("queued", "running") for j in jobs.jobs.values()):
                raise HTTPException(409, _detail("Дождитесь окончания озвучки, потом обновите программу.",
                                                 "Wait until the dub is finished, then update."))
            installed = updater.install()
        except update.UpdateError as exc:
            updating.release()
            print(f"Update failed: {exc}", flush=True)
            raise HTTPException(502, _detail(
                "Не удалось обновить программу. Проверьте интернет и попробуйте ещё раз.",
                "Couldn't update the program. Check the internet and try again.")) from exc
        except BaseException:
            updating.release()
            raise
        if not restart:  # nothing restarts this server: new dubs are fine until the user restarts it
            updating.release()
        if restart:  # after this answer has been sent: the server stops, main() starts the new version
            threading.Timer(0.5, restart).start()
        return {"installed": installed, "restarting": restart is not None}

    @app.get("/api/changelog")
    def changelog() -> list[dict]:
        log = json.loads((Path(__file__).with_name("changelog.json")).read_text(encoding="utf-8"))
        return [{"version": v, **notes} for v, notes in
                sorted(log.items(), key=lambda item: update.version_tuple(item[0]), reverse=True)]

    @app.get("/api/languages")
    def list_languages() -> list[dict]:
        return [lang.public() for lang in languages.LANGUAGES.values()]

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return [j.public() for j in sorted(jobs.jobs.values(), key=lambda j: j.created, reverse=True)]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = jobs.jobs.get(job_id)
        if not job:
            raise HTTPException(404)
        return job.public()

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        job = jobs.cancel(job_id)
        if not job:
            raise HTTPException(404)
        if job.status not in ("cancelled", "running"):
            raise HTTPException(409, _detail("Эта работа уже закончена", "This job has already finished"))
        return job.public()

    @app.get("/api/videos")
    def list_videos() -> list[dict]:
        if not settings.output_dir.is_dir():
            return []
        metas = (_read_meta(f) for f in settings.output_dir.iterdir() if f.is_dir())
        return sorted((m for m in metas if m), key=lambda m: m.get("created", ""), reverse=True)

    @app.get("/api/videos/{video_id}")
    def get_video(video_id: str) -> dict:
        folder = folder_for(video_id)
        meta = _read_meta(folder)
        if not meta:
            raise HTTPException(404)
        segments_file = folder / "segments.json"
        meta["segments"] = json.loads(segments_file.read_text(encoding="utf-8")) if segments_file.exists() else []
        # Other dubs of the same video (another language or voice), for the watch page's switcher.
        meta["siblings"] = [{k: m.get(k) for k in ("id", "target_lang", "voice", "background", "remove_voice")}
                            for m in list_videos() if m["video_id"] == meta["video_id"] and m["id"] != meta["id"]]
        return meta

    @app.delete("/api/videos/{video_id}")
    def delete_video(video_id: str) -> dict:
        shutil.rmtree(folder_for(video_id))
        return {"deleted": video_id}

    def settings_view() -> dict:
        prices = []
        for model_id, model in translate.CLAUDE_MODELS.items():
            per10 = (_TEN_MIN_TOKENS[0] * model.input_usd + _TEN_MIN_TOKENS[1] * model.output_usd) / 1e6
            prices.append({"id": model_id, "label": model.label, "per_10_min_usd": round(per10, 3)})
        return {
            "claude": {"key_set": bool(settings.claude_key), "key_hint": _key_hint(settings.claude_key),
                       "model": settings.claude_model, "models": prices},
            "use_claude": settings.translator in ("auto", "claude"),
            "active": translate.uses_claude(settings.translator, settings.claude_key),
            "glossary": settings.glossary(),
        }

    def busy_jobs() -> bool:
        return any(j.status in ("queued", "running") for j in jobs.jobs.values())

    def refuse_while_dubbing() -> None:
        if busy_jobs():  # a running dub reads and writes its cache
            raise HTTPException(409, _detail("Дождитесь окончания озвучки, потом очистите кэш.",
                                             "Wait until the dub is finished, then clear the cache."))

    @app.get("/api/storage")
    def storage() -> dict:
        work = settings.work_dir
        library: dict[str, list[dict]] = {}
        for meta in list_videos():
            library.setdefault(meta["video_id"], []).append(meta)
        videos = []
        for folder in sorted(work.iterdir()) if work.is_dir() else ():
            if not folder.is_dir() or folder.name == "uploads" or not _ID.match(folder.name):
                continue
            dubs = library.get(folder.name, [])
            title = dubs[0]["title"] if dubs else ""
            if not title:
                with contextlib.suppress(OSError, ValueError, KeyError):
                    title = json.loads((folder / "info.json").read_text(encoding="utf-8"))["title"]
            videos.append({"video_id": folder.name, "title": title or folder.name, "cache": folder_size(folder),
                           "library": sum(folder_size(settings.output_dir / d["id"]) for d in dubs),
                           "dubs": len(dubs)})
        videos.sort(key=lambda v: v["cache"], reverse=True)
        if (uploaded := folder_size(work / "uploads")):  # files not dubbed yet (or whose dub failed)
            videos.append({"video_id": "uploads", "title": "", "cache": uploaded, "library": 0, "dubs": 0})
        return {"cache": sum(v["cache"] for v in videos),
                "uploads": folder_size(work / "uploads"), "library": folder_size(settings.output_dir),
                "models": models_size(), "videos": videos}

    @app.delete("/api/storage/cache/{video_id}")
    def clear_cache(video_id: str) -> dict:
        folder = settings.work_dir / video_id
        if not _ID.match(video_id) or not folder.is_dir():
            raise HTTPException(404)
        refuse_while_dubbing()
        freed = folder_size(folder)
        shutil.rmtree(folder, ignore_errors=True)
        return {"freed": freed}

    @app.delete("/api/storage/cache")
    def clear_all_cache() -> dict:
        refuse_while_dubbing()
        freed = 0
        for folder in settings.work_dir.iterdir() if settings.work_dir.is_dir() else ():
            if folder.is_dir():  # files here (stage_times.json) are this PC's settings, not cache
                freed += folder_size(folder)
                shutil.rmtree(folder, ignore_errors=True)
        return {"freed": freed}

    @app.get("/api/settings")
    def get_settings() -> dict:
        return settings_view()

    @app.put("/api/settings")
    def update_settings(req: SettingsUpdate) -> dict:
        if req.glossary is not None and len(req.glossary) > 20_000:  # validate everything before saving anything
            raise HTTPException(422, _detail("Глоссарий слишком длинный", "The glossary is too long"))
        updates: dict[str, str | None] = {}
        if req.model is not None:
            if req.model not in translate.CLAUDE_MODELS:
                raise HTTPException(422, _detail("Неизвестная модель", "Unknown model"))
            settings.claude_model = updates["DUBBER_CLAUDE_MODEL"] = req.model
        if req.use_claude is not None:
            settings.translator = updates["DUBBER_TRANSLATOR"] = "auto" if req.use_claude else "google"
        if updates:
            save_env(settings.env_file, updates)
        if req.glossary is not None:
            settings.glossary_file.write_text(req.glossary.strip() + "\n", encoding="utf-8")
        return settings_view()

    @app.post("/api/settings/claude-key")
    def set_claude_key(req: KeyRequest) -> dict:
        key = req.key.strip()
        if not key.startswith("sk-ant-") or len(key) < 20 or any(c.isspace() for c in key):
            raise HTTPException(422, _detail("Это не похоже на ключ Anthropic: он начинается с sk-ant- и длиннее. "
                                             "Скопируйте его полностью.",
                                             "This doesn't look like an Anthropic key: it starts with sk-ant- and is "
                                             "longer. Copy it completely."))
        try:
            check_key(key)
        except translate.TranslatorUnavailable as exc:
            ru, en = _KEY_ERRORS.get(exc.code, _KEY_ERRORS["unavailable"])
            raise HTTPException(422, _detail(ru, en)) from None
        settings.claude_key = key
        save_env(settings.env_file, {"ANTHROPIC_API_KEY": key})
        return settings_view()

    @app.delete("/api/settings/claude-key")
    def remove_claude_key() -> dict:
        settings.claude_key = ""
        save_env(settings.env_file, {"ANTHROPIC_API_KEY": None})
        return settings_view()

    @app.get("/files/{video_id}/{name}")
    def get_file(video_id: str, name: str, download: bool = False) -> FileResponse:
        folder = folder_for(video_id)
        meta = _read_meta(folder) or {}
        info = file_info(name, meta.get("target_lang", languages.DEFAULT))
        if info is None or not (folder / name).is_file():
            raise HTTPException(404)
        media_type, download_name = info
        filename = None
        if download and download_name:
            filename = download_name.format(title=pipeline.safe_name(meta.get("title", video_id)))
        # no-cache = the browser may keep a copy but must check with the server first (ETag), as a re-dub
        # replaces files under the same names.
        return FileResponse(folder / name, media_type=media_type, filename=filename,
                            headers={"Cache-Control": "no-cache"})

    app.mount("/", _FreshStaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def _version_body(host: str, port: int, timeout: float) -> bytes:
    """GET /api/version straight to this computer (no proxy settings involved); OSError if nothing answers."""
    import http.client

    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", "/api/version")
        return conn.getresponse().read()
    finally:
        conn.close()


def running_version(host: str, port: int, timeout: float = 1.5) -> str | None:
    """None if nothing listens on the port; else the version of the Dubber already running there ("" = unknown:
    an older Dubber without /api/version, or another program)."""
    try:
        body = _version_body(host, port, timeout)
    except OSError:
        return None
    try:
        return str(json.loads(body)["version"])
    except (ValueError, KeyError, TypeError):
        return ""


def _open_browser_when_ready(url: str, host: str, port: int) -> None:
    for _ in range(60):  # up to ~30 s: open the page only once this server answers (never an old one)
        if running_version(host, port, timeout=0.5) == __version__:
            webbrowser.open(url)
            return
        time.sleep(0.5)


def _start_new_version(open_browser: bool) -> int:
    """Run the version an update just installed (this process still has the old code loaded) and wait for it."""
    env = dict(os.environ, DUBBER_JUST_UPDATED="1")
    if not open_browser:
        env["DUBBER_NO_BROWSER"] = "1"  # the open page reloads itself
    child = subprocess.Popen([sys.executable, "-m", "dubber.app"], env=env)
    while True:  # Ctrl+C reaches both processes: let the new version stop by itself, don't kill it
        try:
            return child.wait()
        except KeyboardInterrupt:
            continue


def shortcut_command(environ=os.environ, platform: str = sys.platform) -> list[str] | None:
    """On Windows, when the program was started without the launcher (an old start file, or the restart after a
    self-update), the command that makes the desktop shortcut the launcher would have made; else None."""
    script = Path(__file__).resolve().parent.parent / "scripts" / "windows" / "dubber.ps1"
    if platform != "win32" or environ.get("DUBBER_LAUNCHER") or not script.is_file():
        return None
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-ShortcutOnly"]


def _make_shortcut(command: list[str]) -> None:
    with contextlib.suppress(OSError, subprocess.SubprocessError):  # no shortcut is not worth stopping for
        subprocess.run(command, capture_output=True, timeout=120,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def update_at_start(updater: update.Updater) -> bool:
    """Install a newer `main` before starting; True if the new version must be started. Never stops the start."""
    if os.environ.get("DUBBER_JUST_UPDATED") or not updater.enabled():
        return False
    latest = updater.latest()
    if not update.is_newer(latest, __version__):
        return False
    print(f"Обновляю «Дубляж» до версии {latest}… (обычно несколько секунд, иногда несколько минут)", flush=True)
    try:
        updater.install()
    except Exception as exc:  # never stop the program from starting
        print(f"Обновить не удалось ({exc}). Запускаю текущую версию {__version__}.", flush=True)
        return False
    return True


def main() -> int:
    import uvicorn

    settings = load_settings()  # also reads .env (e.g. DUBBER_AUTO_UPDATE=0)
    host = os.environ.get("DUBBER_HOST", "127.0.0.1")
    port = int(os.environ.get("DUBBER_PORT", "7860"))
    url = f"http://{host}:{port}"
    other = running_version(host, port)
    if other is not None:
        # Starting a new version while the old window is still open used to show the OLD page.
        which = f"версия {other}" if other else "старая версия"
        print(f"«Дубляж» уже запущен ({which}) на {url}.\n"
              "Закройте другое чёрное окно «Дубляж» и запустите программу снова.")
        return 1
    open_browser = os.environ.get("DUBBER_NO_BROWSER") is None
    updater = update.Updater()
    if update_at_start(updater):
        return _start_new_version(open_browser)
    if command := shortcut_command():
        threading.Thread(target=_make_shortcut, args=(command,), daemon=True).start()
    if open_browser:
        threading.Thread(target=_open_browser_when_ready, args=(url, host, port), daemon=True).start()
    print(f"«Дубляж» {__version__} работает: {url}  (не закрывайте это окно)")
    restarting = threading.Event()
    # A restart must not wait for a paused video another tab is still streaming.
    server = uvicorn.Server(uvicorn.Config(None, host=host, port=port, log_level="warning",
                                           timeout_graceful_shutdown=3))

    def restart() -> None:
        restarting.set()
        server.should_exit = True

    server.config.app = create_app(settings, updater=updater, restart=restart)
    server.run()
    if restarting.is_set():
        print("Запускаю новую версию…", flush=True)
        return _start_new_version(open_browser=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
