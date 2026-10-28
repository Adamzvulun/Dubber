"""Keeps a PC on the newest version of `main` (Adam merges, every PC follows on its next start).

At start `app.main()` asks GitHub for the version on `main`; when it is newer, it downloads `main` as a ZIP, replaces
the program files and starts the new version. The website offers the same as a button when a newer version appears
while it runs. The user's data (`.env`, `glossary.txt`, `work/`, `output/`, `.venv/`, logs) is never touched: those
names are not in the repository, and they are skipped even if they were.

Off in a git checkout (a developer's copy) and with DUBBER_AUTO_UPDATE=0. For a rehearsal without GitHub,
DUBBER_UPDATE_SOURCE=<url> serves `<url>/main/dubber/__init__.py` and `<url>/main.zip` instead.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import subprocess
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

from .config import PROJECT_ROOT

REPO = "Adamzvulun/Dubber"
MANIFEST = ".dubber-files"  # program files the last update installed: files a new version dropped get removed
DEPS_STAMP = ".dubber-deps"  # hash of the pyproject.toml whose components were installed last
KEEP = {".env", "glossary.txt", "work", "output", "models", "ffmpeg", ".venv", "install.log", ".git", MANIFEST,
        DEPS_STAMP}
VERSION_FILE = "dubber/__init__.py"
_VERSION = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.M)

# (url, timeout seconds) -> body
FetchFn = Callable[[str, float], bytes]


class UpdateError(Exception):
    """The update could not be downloaded or installed; the current version keeps working."""


def _fetch(url: str, timeout: float) -> bytes:
    from urllib.request import Request, urlopen

    with urlopen(Request(url, headers={"User-Agent": "Dubber-updater"}), timeout=timeout) as response:
        return response.read()


def version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3])


def is_newer(latest: str | None, current: str) -> bool:
    return bool(latest) and version_tuple(latest) > version_tuple(current)


class Updater:
    def __init__(self, root: Path = PROJECT_ROOT, repo: str = REPO, fetch: FetchFn = _fetch,
                 run: Callable[..., object] = subprocess.run, python: str = sys.executable):
        self.root, self.fetch, self.run, self.python = root, fetch, run, python
        source = os.environ.get("DUBBER_UPDATE_SOURCE")
        self.version_url = (f"{source}/main" if source else f"https://raw.githubusercontent.com/{repo}/main"
                            ) + "/dubber/__init__.py"
        self.zip_url = f"{source}/main.zip" if source else f"https://codeload.github.com/{repo}/zip/refs/heads/main"

    def enabled(self) -> bool:
        return os.environ.get("DUBBER_AUTO_UPDATE", "1") != "0" and not (self.root / ".git").exists()

    def latest(self, timeout: float = 5.0) -> str | None:
        """The version on `main`, or None when GitHub can't be reached (no internet: just start as usual)."""
        try:
            match = _VERSION.search(self.fetch(self.version_url, timeout).decode("utf-8"))
        except Exception:  # offline, proxy, GitHub down, private repo (404)
            return None
        return match.group(1) if match else None

    def install(self, timeout: float = 120.0) -> str:
        """Download `main` and put its files in place; returns the installed version. Raises UpdateError."""
        try:
            data = self.fetch(self.zip_url, timeout)
            files = _read_zip(data)
        except UpdateError:
            raise
        except Exception as exc:
            raise UpdateError(f"download failed: {exc}") from exc
        match = _VERSION.search(files[VERSION_FILE].decode("utf-8"))
        if not match:
            raise UpdateError("the download has no version")
        stamp = _read(self.root / DEPS_STAMP).decode("ascii", "replace").strip()
        new_deps = hashlib.sha1(files["pyproject.toml"]).hexdigest()
        # A PC installed from a ZIP has no stamp yet: its components match the pyproject.toml it came with.
        deps_changed = new_deps != (stamp or hashlib.sha1(_read(self.root / "pyproject.toml")).hexdigest())
        try:
            self._apply(files, deps_changed)
        except OSError as exc:  # e.g. a file locked by antivirus on Windows
            raise UpdateError(f"could not replace the program files: {exc}") from exc
        finally:
            for partial in self.root.rglob("*.partial"):
                if partial.relative_to(self.root).parts[0] not in KEEP:
                    partial.unlink(missing_ok=True)
        return match.group(1)

    def _apply(self, files: dict[str, bytes], deps_changed: bool) -> None:
        """Put the files in place. The version file goes last, only once everything else worked: until then the PC
        still reports its old version, so a failed update is simply tried again on the next start."""
        for name, content in sorted(files.items(), key=lambda item: item[0] == VERSION_FILE):
            if name == VERSION_FILE:
                pip = [self.python, "-m", "pip", "install", "-q", "--upgrade", "--disable-pip-version-check"]
                if deps_changed:  # new or updated components (like install_windows.bat)
                    (self.root / DEPS_STAMP).write_text("pending")  # a failed install is redone next time
                    done = self.run([*pip, "--no-build-isolation", "-e", "."], cwd=self.root)
                    if getattr(done, "returncode", 0):
                        raise UpdateError("installing the new components failed (run install_windows.bat)")
                    (self.root / DEPS_STAMP).write_text(hashlib.sha1(files["pyproject.toml"]).hexdigest())
                self.run([*pip, "yt-dlp"], cwd=self.root)  # YouTube changes often; a fresh downloader fixes most
            target = self.root / name
            if _read(target) == content:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".partial")
            partial.write_bytes(content)
            partial.replace(target)
        manifest = self.root / MANIFEST
        for name in set(_read(manifest).decode("utf-8", "replace").splitlines()) - set(files):
            if _safe_name(name):
                (self.root / name).unlink(missing_ok=True)
        manifest.write_text("\n".join(sorted(files)) + "\n", encoding="utf-8")


def _safe_name(name: str) -> bool:
    """A plain relative path inside the program folder, outside the user's data (no "..", drive or backslash)."""
    parts = name.split("/")
    return (bool(name) and "\\" not in name and ":" not in name and parts[0] not in KEEP
            and all(p not in ("", ".", "..") for p in parts))


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        return b""


def _read_zip(data: bytes) -> dict[str, bytes]:
    """{path inside the repository: content} from GitHub's ZIP of a branch (one top folder, e.g. "Dubber-main/")."""
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for item in archive.infolist():
            name = item.filename.partition("/")[2]
            if not item.is_dir() and _safe_name(name):
                files[name] = archive.read(item)
    if VERSION_FILE not in files or "pyproject.toml" not in files:
        raise UpdateError("the download is not a Dubber version")
    return files
