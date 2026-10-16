"""The Dubber website: a small FastAPI server + a hand-built front-end in dubber/web/.

Run: `python -m dubber.app` → opens http://127.0.0.1:7860

API
- POST /api/jobs {url, voice: "male"|"female", background: bool, lang} → start dubbing (one job at a time)
- GET  /api/languages                                              → dub languages (code, names, voices)
- GET  /api/jobs, /api/jobs/{id}                                   → progress
- POST /api/jobs/{id}/cancel                                        → stop a queued or running job
- GET  /api/videos, /api/videos/{id}                                → library, one video + its timed transcript
- DELETE /api/videos/{id}                                           → remove from the library
- GET  /files/{id}/{name}[?download=1]                               → video, subtitles, transcripts, thumbnail
"""

from __future__ import annotations

import dataclasses
import json
import os
import queue
import re
import shutil
import threading
import time
import traceback
import uuid
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import languages, pipeline
from .config import Settings, load_settings
from .download import is_url

WEB_DIR = Path(__file__).parent / "web"
STAGE_KEYS = {label: key for key, label, _ in pipeline.STAGES}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

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
    status: str = "queued"  # queued | running | done | error | cancelled
    stage: str = ""
    label: str = "В очереди"
    progress: float = 0.0
    error: str = ""  # Russian
    error_en: str = ""
    video_id: str = ""
    created: float = field(default_factory=time.time)
    cancel_requested: bool = False

    def public(self) -> dict:
        return dataclasses.asdict(self)


class JobCancelled(Exception):
    """Raised from the progress callback to stop a job the user cancelled."""


class JobRunner:
    """Runs dubbing jobs one after another in a background thread."""

    def __init__(self, settings: Settings, runner=pipeline.run):
        self.settings = settings
        self.runner = runner
        self.jobs: dict[str, Job] = {}
        self._queue: queue.Queue[Job] = queue.Queue()
        threading.Thread(target=self._work, daemon=True).start()

    def submit(self, url: str, voice: str, background: bool, lang: str = languages.DEFAULT) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], url=url, voice=voice, background=background, lang=lang)
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
            job.status, job.label = "running", "Начинаю"
            settings = dataclasses.replace(
                self.settings, target_lang=job.lang, voice=languages.voice_for(job.lang, job.voice),
                keep_background=job.background,
            )

            def progress(label: str, fraction: float, job: Job = job) -> None:
                # Called at the start of every stage and often inside long ones (download, Whisper, TTS).
                if job.cancel_requested:
                    raise JobCancelled()
                job.stage, job.label, job.progress = STAGE_KEYS.get(label, ""), label, round(fraction, 4)

            try:
                result = self.runner(job.url, settings, progress=progress)
                job.video_id, job.status, job.progress, job.label = result.id, "done", 1.0, "Готово"
            except Exception as exc:  # shown to the user in Russian
                if job.cancel_requested:  # yt-dlp may wrap our JobCancelled in its own error
                    job.status, job.label = "cancelled", "Отменено"
                    continue
                traceback.print_exc()
                job.status, job.error, job.error_en = "error", friendly_error(exc), friendly_error(exc, "en")


class JobRequest(BaseModel):
    url: str
    voice: str = "male"
    background: bool = True
    lang: str = languages.DEFAULT


def _read_meta(folder: Path) -> dict | None:
    try:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (folder / "dubbed.mp4").exists():
        return None
    meta["thumbnail"] = f"/files/{folder.name}/thumbnail.jpg"
    meta["video"] = f"/files/{folder.name}/dubbed.mp4"
    if "target_lang" not in meta:  # dubbed before other languages existed: English → Russian, old file names
        meta.update(target_lang="ru", source_lang="en", files=LEGACY_FILES)
    return meta


def create_app(settings: Settings | None = None, runner=pipeline.run) -> FastAPI:
    settings = settings or load_settings()
    jobs = JobRunner(settings, runner)
    app = FastAPI(title="Дубляж", docs_url=None, redoc_url=None)

    def folder_for(video_id: str) -> Path:
        if not _ID.match(video_id):
            raise HTTPException(404)
        folder = settings.output_dir / video_id
        if not folder.is_dir():
            raise HTTPException(404)
        return folder

    @app.post("/api/jobs")
    def start_job(req: JobRequest) -> dict:
        url = req.url.strip()
        if not is_url(url):
            raise HTTPException(422, _detail("Вставьте ссылку на видео — она начинается с https://",
                                             "Paste a video link — it starts with https://"))
        if req.voice not in ("male", "female"):
            raise HTTPException(422, _detail("Неизвестный голос", "Unknown voice"))
        if req.lang not in languages.LANGUAGES:
            raise HTTPException(422, _detail("Неизвестный язык", "Unknown language"))
        return jobs.submit(url, req.voice, req.background, req.lang).public()

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
        return meta

    @app.delete("/api/videos/{video_id}")
    def delete_video(video_id: str) -> dict:
        shutil.rmtree(folder_for(video_id))
        return {"deleted": video_id}

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
        return FileResponse(folder / name, media_type=media_type, filename=filename)

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def main() -> None:
    import uvicorn

    host = os.environ.get("DUBBER_HOST", "127.0.0.1")
    port = int(os.environ.get("DUBBER_PORT", "7860"))
    if os.environ.get("DUBBER_NO_BROWSER") is None:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    print(f"«Дубляж» работает: http://{host}:{port}  (не закрывайте это окно)")
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
