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
"Install" walks its 3 steps in ~12 s (STUB_CLONE_FAIL=1: fails at step 2), then "Original" is offered on the form
(STUB_CUDA=broken: installed, but PyTorch can't compute on the card).
The phone (phone.py): STUB_MAILBOX=<mailbox address> STUB_TUNNEL=<tunnel address> connects the stand-in PC to the
local stand-in for Cloudflare, `node tools/phone_dev.mjs` (no cloudflared: the tunnel address is reported at once).
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

from dubber import app, clone, download, phone, pipeline
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
        self._step_started = 0.0

    def status(self) -> dict:
        gpu = {"none": None, "small": {"name": "NVIDIA GeForce GTX 1650", "vram_gb": 4.0}}.get(
            os.environ.get("STUB_GPU", ""), {"name": "NVIDIA GeForce RTX 3070", "vram_gb": 8.0})
        cuda = {"available": True, "name": gpu and gpu["name"], "cuda": "12.8"}
        if os.environ.get("STUB_CUDA") == "broken":
            cuda = {"available": False, "error": "CUDA error: no kernel image is available for execution on the device"}
        return {"gpu": gpu, "gpu_ok": bool(gpu and gpu["vram_gb"] >= clone.MIN_VRAM_GB), "installed": self.ready,
                "ready": self.ready, "min_vram_gb": clone.MIN_VRAM_GB, "unsupported": sorted(clone.UNSUPPORTED),
                "cuda": cuda if self.ready else None}

    def start(self, steps=None) -> bool:
        if self.state["running"]:
            return False
        self.state.update(running=True, error="", done=False)
        threading.Thread(target=self._install, daemon=True).start()
        return True

    def progress(self) -> float | None:
        """Like clone.Installer.progress: the share done, filled evenly over each 4-second step."""
        if not self.state["running"] or self.state["step"] not in clone.STEP_SHARES:
            return None
        steps = list(clone.STEP_SHARES)
        done = sum(clone.STEP_SHARES[s] for s in steps[:steps.index(self.state["step"])])
        into = min(0.97, (time.monotonic() - self._step_started) / 4)
        return round(done + clone.STEP_SHARES[self.state["step"]] * into, 3)

    def _install(self) -> None:
        for step in clone.Installer.STEPS:
            self.state["step"] = step
            self._step_started = time.monotonic()
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
                        glossary_file=data / "glossary.txt", cookies_file=data / "cookies.txt", claude_key="",
                        translator="auto")
    print(f"Stub Dubber on http://127.0.0.1:{port} (library: {settings.output_dir})", flush=True)
    download.playlist_entries = fake_playlist
    stub_clone = StubClone()
    clone.cuda_ok = lambda run=None: os.environ.get("STUB_CUDA") != "broken"  # the stand-in card computes (or not)
    bridge = None
    if os.environ.get("STUB_MAILBOX"):
        os.environ["DUBBER_MAILBOX_URL"] = os.environ["STUB_MAILBOX"]
        phone.PULL_EVERY = float(os.environ.get("STUB_PULL", phone.PULL_EVERY))  # seconds between mailbox checks
        tunnel_url = os.environ.get("STUB_TUNNEL", f"http://127.0.0.1:{port}")

        class StubTunnel:
            def __init__(self, exe, port, on_url):
                self.on_url = on_url

            def run(self):
                self.on_url(tunnel_url)

            def stop(self):
                pass

        def bridge(submit):
            return phone.PhoneBridge(settings.env_file, port, submit, tools=data / "cf", tunnel_factory=StubTunnel,
                                     download=lambda tools: Path("cloudflared")).start()
    site = app.create_app(settings, runner=runner, check_key=check_key, updater=StubUpdater(),
                          clone_status=stub_clone.status, installer=stub_clone, phone_bridge=bridge)
    uvicorn.run(site, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
