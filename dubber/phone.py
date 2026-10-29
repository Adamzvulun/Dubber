"""Dubber on the phone (ADR-033): the phone sends links, this PC dubs them.

    phone app ──► mailbox (Cloudflare Worker, cloud/worker/) ◄── this PC: "my address is …", "any links for me?"
        └──────────► this PC through a free Cloudflare quick tunnel (https://<words>.trycloudflare.com)

- No account and nothing to click: `cloudflared` (one file) is downloaded into the program folder on the first start,
  and the tunnel starts with the program. Its address changes at every start; the PC tells the mailbox.
- The household's secret token (made once, kept in .env) is part of the phone app's address (the QR code in
  Settings → «Телефон») and goes with every request: the mailbox keeps one box per token, and requests that come
  through the tunnel without it are refused (app.py).
- PC switched off: the phone leaves links in the mailbox; `PhoneBridge` picks them up every minute and starts the dubs.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .config import PROJECT_ROOT, save_env

# Adam's mailbox (cloud/worker/), set once it is deployed; DUBBER_MAILBOX_URL overrides it (tests, a second mailbox)
MAILBOX_URL = ""
TOKEN_KEY = "DUBBER_PHONE_TOKEN"
TOOLS_DIR = PROJECT_ROOT / "cloudflared"  # cloudflared lives here (git-ignored, kept by updates like ffmpeg/)
RELEASES = "https://github.com/cloudflare/cloudflared/releases/latest/download/"
TUNNEL_URL = re.compile(r"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com")
PULL_EVERY = 60  # seconds between "any links for me?"
ANNOUNCE_EVERY = 300  # seconds between "my address is …" (the phone shows when the PC was last seen)


def enabled() -> bool:
    return os.environ.get("DUBBER_PHONE", "1").lower() not in ("0", "false", "no")


def mailbox_url() -> str:
    return (os.environ.get("DUBBER_MAILBOX_URL") or MAILBOX_URL).rstrip("/")


def household_token(env_file: Path) -> str:
    """This household's secret (43 letters), made on the first start and kept in .env."""
    token = os.environ.get(TOKEN_KEY, "")
    if not token and env_file.is_file():  # .env is read at start, but not when settings live elsewhere (tests, stub)
        found = re.search(rf"^{TOKEN_KEY}=(\S+)", env_file.read_text(encoding="utf-8"), re.M)
        token = found.group(1) if found else ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", token):
        token = secrets.token_urlsafe(32)
        env_file.parent.mkdir(parents=True, exist_ok=True)
        save_env(env_file, {TOKEN_KEY: token})
    return token


def pair_url(token: str, mailbox: str | None = None) -> str:
    """The phone app's address for this household: the QR code in Settings → «Телефон»."""
    return f"{mailbox if mailbox is not None else mailbox_url()}/p/{token}/"


# ---------- cloudflared ----------

def cloudflared_asset(system: str = sys.platform, machine: str = platform.machine()) -> str | None:
    """The file to download from cloudflared's GitHub releases for this computer (None: not offered)."""
    arm = machine.lower() in ("arm64", "aarch64")
    if system == "win32":
        return "cloudflared-windows-amd64.exe" if machine.lower() in ("amd64", "x86_64", "arm64") else \
            "cloudflared-windows-386.exe"
    if system.startswith("linux"):
        return "cloudflared-linux-arm64" if arm else "cloudflared-linux-amd64"
    if system == "darwin":
        return "cloudflared-darwin-arm64.tgz" if arm else "cloudflared-darwin-amd64.tgz"
    return None


def cloudflared_path(tools: Path = TOOLS_DIR, system: str = sys.platform) -> Path:
    return tools / ("cloudflared.exe" if system == "win32" else "cloudflared")


def find_cloudflared(tools: Path = TOOLS_DIR) -> Path | None:
    local = cloudflared_path(tools)
    if local.is_file():
        return local
    found = shutil.which("cloudflared")
    return Path(found) if found else None


def download_cloudflared(tools: Path = TOOLS_DIR, opener=urllib.request.urlopen, asset: str | None = None) -> Path:
    """Download cloudflared (about 40 MB, once) into the program folder."""
    asset = asset or cloudflared_asset()
    if asset is None:
        raise RuntimeError(f"cloudflared is not offered for {sys.platform}/{platform.machine()}")
    tools.mkdir(parents=True, exist_ok=True)
    target = cloudflared_path(tools)
    part = tools / (asset + ".part")
    with opener(RELEASES + asset, timeout=60) as response, open(part, "wb") as out:
        shutil.copyfileobj(response, out)
    if asset.endswith(".tgz"):
        with tarfile.open(part) as archive:
            member = next(m for m in archive.getmembers() if m.isfile() and Path(m.name).name == "cloudflared")
            with archive.extractfile(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
        part.unlink()
    else:
        os.replace(part, target)
    target.chmod(0o755)
    return target


class Tunnel:
    """`cloudflared tunnel --url http://127.0.0.1:<port>`, restarted when it stops; reports its address."""

    def __init__(self, exe: Path, port: int, on_url: Callable[[str | None], None], popen=subprocess.Popen,
                 sleep: Callable[[float], None] = time.sleep):
        self.exe, self.port, self.on_url, self.popen, self.sleep = exe, port, on_url, popen, sleep
        self.url: str | None = None
        self._proc = None
        self._stop = threading.Event()

    def run(self) -> None:
        """Keep the tunnel up until stop(): call in a thread."""
        delay = 5.0
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                # No CREATE_NO_WINDOW: it shares the program's console, so closing that window closes it too.
                self._proc = self.popen(
                    [str(self.exe), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.port}"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace")
                for line in self._proc.stderr:
                    found = TUNNEL_URL.search(line)
                    if found and found.group(0) != self.url:
                        self.url = found.group(0)
                        self.on_url(self.url)
                self._proc.wait()
            except OSError:
                pass
            if self.url is not None:
                self.url = None
                self.on_url(None)
            if self._stop.is_set():
                break
            delay = 5.0 if time.monotonic() - started > 300 else min(delay * 2, 120.0)
            self.sleep(delay)

    def stop(self) -> None:
        self._stop.set()
        if self._proc is not None and self._proc.poll() is None:
            with contextlib.suppress(OSError):
                self._proc.terminate()


# ---------- mailbox ----------

class Mailbox:
    """The household's box in the mailbox worker (cloud/worker/worker.js)."""

    def __init__(self, base: str, token: str, opener=urllib.request.urlopen):
        self.base, self.token, self.opener = base.rstrip("/"), token, opener

    def _call(self, method: str, path: str, body: dict | None = None):
        request = urllib.request.Request(
            self.base + path, method=method, data=None if body is None else json.dumps(body).encode(),
            headers={"X-Dubber-Token": self.token, "Content-Type": "application/json",
                     "User-Agent": f"Dubber/{__version__}"})
        with self.opener(request, timeout=20) as response:
            return json.loads(response.read() or b"null")

    def announce(self, url: str) -> None:
        self._call("PUT", "/api/box/pc", {"url": url, "version": __version__})

    def links(self) -> list[dict]:
        return self._call("GET", "/api/box").get("links", [])

    def delete(self, link_id: str) -> None:
        self._call("DELETE", f"/api/box/links/{link_id}")


class PhoneBridge:
    """Keeps this PC reachable from the household's phones and dubs the links they left while it was off."""

    def __init__(self, env_file: Path, port: int, submit: Callable[[dict], None], *, tools: Path = TOOLS_DIR,
                 mailbox: Mailbox | None = None, tunnel_factory=Tunnel, download=download_cloudflared,
                 clock: Callable[[], float] = time.monotonic):
        self.port, self.submit, self.tools, self.download, self.clock = port, submit, tools, download, clock
        self.token = household_token(env_file)
        base = mailbox_url()
        self.mailbox = mailbox or (Mailbox(base, self.token) if base else None)
        self.tunnel_factory = tunnel_factory
        self.status = "starting"  # starting | downloading | ready | waiting (no tunnel yet) | error | unconfigured
        self.url: str | None = None
        self.tunnel: Tunnel | None = None
        self._announced = 0.0
        self._wake = threading.Event()
        self._stop = threading.Event()

    def public(self) -> dict:
        return {"status": self.status, "pair_url": pair_url(self.token) if self.mailbox else None,
                "connected": self.url is not None, "address": self.url}

    def start(self) -> PhoneBridge:
        if self.mailbox is None:
            self.status = "unconfigured"
            return self
        threading.Thread(target=self._run, daemon=True, name="phone").start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self.tunnel is not None:
            self.tunnel.stop()

    def _on_url(self, url: str | None) -> None:
        self.url = url
        self.status = "ready" if url else "waiting"
        self._announced = 0.0
        self._wake.set()

    def _run(self) -> None:
        exe = find_cloudflared(self.tools)
        if exe is None:
            self.status = "downloading"
            try:
                exe = self.download(self.tools)
            except (OSError, urllib.error.URLError, RuntimeError, tarfile.TarError, StopIteration) as exc:
                print(f"Телефон: не удалось скачать cloudflared ({exc}). Попробую при следующем запуске.", flush=True)
                self.status = "error"
                exe = None
        if exe is not None:
            self.status = "waiting"
            self.tunnel = self.tunnel_factory(exe, self.port, self._on_url)
            threading.Thread(target=self.tunnel.run, daemon=True, name="tunnel").start()
        while not self._stop.is_set():
            self.tick()
            self._wake.wait(PULL_EVERY)
            self._wake.clear()

    def tick(self) -> None:
        """Say where this PC is (when that changed or every few minutes) and start the dubs waiting in the box."""
        try:
            if self.url and (not self._announced or self.clock() - self._announced > ANNOUNCE_EVERY):
                self.mailbox.announce(self.url)
                self._announced = self.clock()
            for link in self.mailbox.links():
                self.submit(link)
                self.mailbox.delete(link["id"])
        except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
            print(f"Телефон: почтовый ящик недоступен ({exc}).", flush=True)
