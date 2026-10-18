"""Run the real Dubber website with a stand-in pipeline — for UI work and QA without network or models.

    .venv/bin/python tools/stub_server.py [DATA_DIR] [PORT]        # default: /tmp/dubber-stub 7871

The stand-in walks through all 6 stages (~31 s; 7 stages, ~39 s, with "remove the speaker's voice"), uneven per
stage, a progress report every 0.25 s, so Cancel works, and then reports video id "vid". A URL containing "fail"
ends with a download error instead (to see the error card).
Put real finished videos into DATA_DIR/out/<id>/ (e.g. copied from output/) to test the library and watch pages.
Settings are saved in DATA_DIR (never the project's .env); a Claude key ending in "bad" is refused, any other
key-shaped one is accepted without calling Anthropic.
STUB_UPDATE=9.9.9 makes the site offer an update to that version (installing it takes 2 s and changes nothing).
Kill it by PID, never with `pkill -f` (that kills your own shell).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from dubber import app, pipeline
from dubber.config import Settings
from dubber.translate import TranslatorUnavailable

# Seconds per stage, uneven like a real dub (Whisper is the slow part), so the time-left estimate has work to do.
STAGE_SECONDS = {"download": 3, "transcribe": 14, "translate": 2, "tts": 7, "align": 2, "separate": 8, "mux": 3}


def runner(url: str, settings: Settings, progress) -> SimpleNamespace:
    done = 0.0
    for key, label, weight in pipeline.stages(settings.keep_background and settings.remove_voice):
        steps = STAGE_SECONDS[key] * 4
        for i in range(steps):
            progress(label, done + weight * i / steps)
            time.sleep(0.25)
        done += weight
    if "fail" in url:
        raise RuntimeError("DownloadError: HTTP Error 403")
    return SimpleNamespace(id="vid")


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


def main() -> None:
    data = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/dubber-stub")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7871
    settings = Settings(work_dir=data / "w", output_dir=data / "out", env_file=data / ".env",
                        glossary_file=data / "glossary.txt", claude_key="", translator="auto")
    print(f"Stub Dubber on http://127.0.0.1:{port} (library: {settings.output_dir})", flush=True)
    site = app.create_app(settings, runner=runner, check_key=check_key, updater=StubUpdater())
    uvicorn.run(site, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
