"""The Dubber website: a small FastAPI server + a hand-built front-end in dubber/web/.

Run: `python -m dubber.app` → opens http://127.0.0.1:7860

API
- POST /api/jobs {url, voice: "male"|"female", background: bool} → start dubbing (one job runs at a time)
- GET  /api/jobs, /api/jobs/{id}                                   → progress
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
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import pipeline
from .config import Settings, load_settings
from .download import is_url

WEB_DIR = Path(__file__).parent / "web"
VOICES = {"male": "ru-RU-DmitryNeural", "female": "ru-RU-SvetlanaNeural"}
STAGE_KEYS = {label: key for key, label, _ in pipeline.STAGES}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Files the browser may fetch from output/<id>/, with the name used when downloading.
FILES = {
    "dubbed.mp4": ("video/mp4", "{title} (RU).mp4"),
    "subtitles_ru.vtt": ("text/vtt", None),
    "subtitles_en.vtt": ("text/vtt", None),
    "subtitles_ru.srt": ("application/x-subrip", "{title} (RU).srt"),
    "subtitles_en.srt": ("application/x-subrip", "{title} (EN).srt"),
    "transcript_ru.txt": ("text/plain; charset=utf-8", "{title} — текст.txt"),
    "transcript_en_ru.txt": ("text/plain; charset=utf-8", "{title} — EN+RU.txt"),
    "thumbnail.jpg": ("image/jpeg", None),
}


def friendly_error(exc: Exception) -> str:
    """Turn a technical error into a short Russian explanation with what to do."""
    text = f"{type(exc).__name__}: {exc}".lower()
    if "ffmpeg" in text and "not found" in text:
        return "Не найдена программа ffmpeg. Запустите установку ещё раз (install_windows.bat)."
    if "not a bot" in text or "sign in to confirm" in text:
        return (
            "YouTube попросил подтвердить, что вы не робот. "
            "Попробуйте позже или настройте файл cookies (см. инструкцию)."
        )
    if any(w in text for w in ("huggingface", "hf.co", "cas client", "xet")):
        return (
            "Не удалось скачать модель распознавания речи (она скачивается один раз, около 500 МБ). "
            "Проверьте интернет и попробуйте снова. Если ошибка повторяется — возможно, антивирус или сеть "
            "блокируют сайт huggingface.co."
        )
    if "no audio was received" in text:
        return (
            "Сервис озвучки Microsoft сейчас не отвечает. Подождите несколько минут и нажмите «Попробовать снова» — "
            "уже готовые части сохранятся."
        )
    if "downloaderror" in text or "youtube" in text or "unsupported url" in text:
        return (
            "Не удалось скачать видео. Проверьте, что ссылка правильная и интернет работает. "
            "Если ошибка повторяется — запустите установку ещё раз, она обновит загрузчик."
        )
    if "английской речи" in text:
        return "В этом видео не найдено английской речи."
    if any(w in text for w in ("connect", "timeout", "network", "dns", "proxy", "ssl")):
        return "Нет связи с интернет-сервисом перевода или озвучки. Проверьте интернет и попробуйте снова."
    return f"Что-то пошло не так. Попробуйте ещё раз. Подробности для помощника: {exc}"


@dataclass
class Job:
    id: str
    url: str
    voice: str
    background: bool
    status: str = "queued"  # queued | running | done | error
    stage: str = ""
    label: str = "В очереди"
    progress: float = 0.0
    error: str = ""
    video_id: str = ""
    created: float = field(default_factory=time.time)

    def public(self) -> dict:
        return dataclasses.asdict(self)


class JobRunner:
    """Runs dubbing jobs one after another in a background thread."""

    def __init__(self, settings: Settings, runner=pipeline.run):
        self.settings = settings
        self.runner = runner
        self.jobs: dict[str, Job] = {}
        self._queue: queue.Queue[Job] = queue.Queue()
        threading.Thread(target=self._work, daemon=True).start()

    def submit(self, url: str, voice: str, background: bool) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], url=url, voice=voice, background=background)
        self.jobs[job.id] = job
        self._queue.put(job)
        return job

    def _work(self) -> None:
        while True:
            job = self._queue.get()
            job.status, job.label = "running", "Начинаю"
            settings = dataclasses.replace(self.settings, voice=VOICES[job.voice], keep_background=job.background)

            def progress(label: str, fraction: float, job: Job = job) -> None:
                job.stage, job.label, job.progress = STAGE_KEYS.get(label, ""), label, round(fraction, 4)

            try:
                result = self.runner(job.url, settings, progress=progress)
                job.video_id, job.status, job.progress, job.label = result.id, "done", 1.0, "Готово"
            except Exception as exc:  # shown to the user in Russian
                traceback.print_exc()
                job.status, job.error = "error", friendly_error(exc)


class JobRequest(BaseModel):
    url: str
    voice: str = "male"
    background: bool = True


def _read_meta(folder: Path) -> dict | None:
    try:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (folder / "dubbed.mp4").exists():
        return None
    meta["thumbnail"] = f"/files/{folder.name}/thumbnail.jpg"
    meta["video"] = f"/files/{folder.name}/dubbed.mp4"
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
            raise HTTPException(422, "Вставьте ссылку на видео — она начинается с https://")
        if req.voice not in VOICES:
            raise HTTPException(422, "Неизвестный голос")
        return jobs.submit(url, req.voice, req.background).public()

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return [j.public() for j in sorted(jobs.jobs.values(), key=lambda j: j.created, reverse=True)]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = jobs.jobs.get(job_id)
        if not job:
            raise HTTPException(404)
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
        if name not in FILES or not (folder / name).is_file():
            raise HTTPException(404)
        media_type, download_name = FILES[name]
        filename = None
        if download and download_name:
            meta = _read_meta(folder) or {}
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
