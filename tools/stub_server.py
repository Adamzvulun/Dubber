"""Run the real Dubber website with a stand-in pipeline — for UI work and QA without network or models.

    .venv/bin/python tools/stub_server.py [DATA_DIR] [PORT]        # default: /tmp/dubber-stub 7871

The stand-in walks through all 6 stages (~30 s, a progress report every 0.25 s, so Cancel works) and then reports
video id "vid". A URL containing "fail" ends with a download error instead (to see the error card).
Put real finished videos into DATA_DIR/out/<id>/ (e.g. copied from output/) to test the library and watch pages.
Settings are saved in DATA_DIR (never the project's .env); a Claude key ending in "bad" is refused, any other
key-shaped one is accepted without calling Anthropic.
Kill it by PID, never with `pkill -f` (that kills your own shell).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from dubber import app, pipeline
from dubber.config import Settings
from dubber.translate import TranslatorUnavailable


def runner(url: str, settings: Settings, progress) -> SimpleNamespace:
    for _key, label, _weight in pipeline.STAGES:
        for i in range(20):
            progress(label, 0.05 * i)
            time.sleep(0.25)
    if "fail" in url:
        raise RuntimeError("DownloadError: HTTP Error 403")
    return SimpleNamespace(id="vid")


def check_key(key: str) -> None:
    if key.endswith("bad"):
        raise TranslatorUnavailable("stub: refused", code="auth")


def main() -> None:
    data = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/dubber-stub")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7871
    settings = Settings(work_dir=data / "w", output_dir=data / "out", env_file=data / ".env",
                        glossary_file=data / "glossary.txt", claude_key="", translator="auto")
    print(f"Stub Dubber on http://127.0.0.1:{port} (library: {settings.output_dir})", flush=True)
    site = app.create_app(settings, runner=runner, check_key=check_key)
    uvicorn.run(site, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
