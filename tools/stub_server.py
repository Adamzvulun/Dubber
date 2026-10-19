"""Run the real Dubber website with a stand-in pipeline — for UI work and QA without network or models.

    .venv/bin/python tools/stub_server.py [DATA_DIR] [PORT]        # default: /tmp/dubber-stub 7871

The stand-in walks through all 6 stages (~31 s; 7 stages, ~39 s, with "remove the speaker's voice"), uneven per
stage, a progress report every 0.25 s, so Cancel works, and then reports video id "vid". A URL containing "fail"
ends with a download error instead (to see the error card).
Put real finished videos into DATA_DIR/out/<id>/ (e.g. copied from output/) to test the library and watch pages.
Settings are saved in DATA_DIR (never the project's .env); a Claude key ending in "bad" is refused, any other
key-shaped one is accepted without calling Anthropic.
Playlist links get a made-up playlist of 3 videos (15 when the list id starts with "BIG"; no YouTube needed).
STUB_UPDATE=9.9.9 makes the site offer an update to that version (installing it takes 2 s and changes nothing).
The original voice (Settings): the stand-in PC has an RTX 3070 (STUB_GPU=none: no NVIDIA card, STUB_GPU=small: 4 GB);
"Install" walks its 3 steps in ~12 s (STUB_CLONE_FAIL=1: fails at step 2), then "Original" is offered on the form.
Kill it by PID, never with `pkill -f` (that kills your own shell).
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from dubber import app, clone, download, pipeline
from dubber.config import Settings
from dubber.translate import TranslatorUnavailable

# Seconds per stage, uneven like a real dub (Whisper is the slow part), so the time-left estimate has work to do.
STAGE_SECONDS = {"download": 3, "transcribe": 14, "translate": 2, "tts": 7, "align": 2, "separate": 8, "mux": 3}


def runner(url: str, settings: Settings, progress) -> SimpleNamespace:
    done = 0.0
    use_clone = pipeline.clone_choice(settings)[0]
    separate = settings.keep_background and settings.remove_voice or use_clone
    for key, label, weight in pipeline.stages(separate, use_clone):
        steps = STAGE_SECONDS[key] * 4
        for i in range(steps):
            progress(label, done + weight * i / steps)
            time.sleep(0.25)
        done += weight
    if "fail" in url:
        raise RuntimeError("DownloadError: HTTP Error 403")
    return SimpleNamespace(id="vid")


def fake_playlist(url: str, limit: int = 200) -> dict:
    count = 15 if "list=BIG" in url else 3
    entries = [{"url": f"https://www.youtube.com/watch?v=stubvideo{i:02d}", "title": f"Видео {i}"}
               for i in range(1, count + 1)]
    return {"title": "Тестовый плейлист", "entries": entries}


def check_key(key: str) -> None:
    if key.endswith("bad"):
        raise TranslatorUnavailable("stub: refused", code="auth")


class StubUpdater:
    """Pretends `main` has version STUB_UPDATE (unset: no update)."""

    def enabled(self) -> bool:
        return True

    def latest(self, timeout: float = 5.0) -> str | None:
        return os.environ.get("STUB_UPDATE")

    def install(self, timeout: float = 120.0) -> str:
        time.sleep(2)
        return os.environ["STUB_UPDATE"]


class StubClone:
    """A stand-in graphics card and installer for the original voice."""

    def __init__(self):
        self.ready = False
        self.state = {"running": False, "step": "", "error": "", "done": False}

    def status(self) -> dict:
        gpu = {"none": None, "small": {"name": "NVIDIA GeForce GTX 1650", "vram_gb": 4.0}}.get(
            os.environ.get("STUB_GPU", ""), {"name": "NVIDIA GeForce RTX 3070", "vram_gb": 8.0})
        return {"gpu": gpu, "gpu_ok": bool(gpu and gpu["vram_gb"] >= clone.MIN_VRAM_GB), "installed": self.ready,
                "ready": self.ready, "min_vram_gb": clone.MIN_VRAM_GB, "unsupported": sorted(clone.UNSUPPORTED)}

    def start(self) -> bool:
        if self.state["running"]:
            return False
        self.state.update(running=True, error="", done=False)
        threading.Thread(target=self._install, daemon=True).start()
        return True

    def _install(self) -> None:
        for step in clone.Installer.STEPS:
            self.state["step"] = step
            time.sleep(4)
            if step == "omnivoice" and os.environ.get("STUB_CLONE_FAIL"):
                self.state.update(running=False, error=step)
                return
        self.ready = True
        clone.ready = lambda: True  # the stand-in pipeline now treats the original voice as installed
        self.state.update(running=False, done=True)


def main() -> None:
    data = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/dubber-stub")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7871
    settings = Settings(work_dir=data / "w", output_dir=data / "out", env_file=data / ".env",
                        glossary_file=data / "glossary.txt", claude_key="", translator="auto")
    print(f"Stub Dubber on http://127.0.0.1:{port} (library: {settings.output_dir})", flush=True)
    download.playlist_entries = fake_playlist
    stub_clone = StubClone()
    site = app.create_app(settings, runner=runner, check_key=check_key, updater=StubUpdater(),
                          clone_status=stub_clone.status, installer=stub_clone)
    uvicorn.run(site, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
