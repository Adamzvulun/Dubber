"""Speech recognition on the NVIDIA card (ADR-034): NVIDIA's libraries fetched by the program itself, no clicks.

Whisper (ctranslate2) uses an NVIDIA card when the driver is there, but needs NVIDIA's cuBLAS 12 and cuDNN 9 DLLs,
which neither Python nor the driver brings: without them every dub failed on such a PC ("cublas64_12.dll is not
found", Adam's new PC, 2026-10-29). Now:
- transcribe.py falls back to the processor when the card fails, so a dub never fails for this;
- on a Windows PC with an NVIDIA card, the program installs the two pip packages (about 1 GB, once) in the
  background at start (`Installer`), and `use_dll_dirs()` lets ctranslate2 find their DLLs: recognition then runs on
  the card, several times faster.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import sysconfig
import threading
import time
from importlib import metadata
from pathlib import Path

log = logging.getLogger(__name__)

PACKAGES = ("nvidia-cublas-cu12", "nvidia-cudnn-cu12>=9,<10")  # what ctranslate2 4.5+ (CUDA 12) loads
_dll_handles: list = []  # os.add_dll_directory() undoes itself when its handle is garbage-collected


def dll_dirs(site_packages: Path | None = None) -> list[Path]:
    """The folders with NVIDIA's DLLs inside the program's Python, when they are installed."""
    base = (site_packages or Path(sysconfig.get_paths()["purelib"])) / "nvidia"
    return [d for d in (base / "cublas" / "bin", base / "cudnn" / "bin") if d.is_dir()]


def use_dll_dirs(site_packages: Path | None = None, system: str = sys.platform) -> list[Path]:
    """Let ctranslate2 find NVIDIA's DLLs (Windows; elsewhere they must be on the library path before start)."""
    if system != "win32":
        return []
    dirs = dll_dirs(site_packages)
    path = os.environ.get("PATH", "")
    for d in dirs:
        if str(d) not in path.split(os.pathsep):
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            _dll_handles.append(os.add_dll_directory(str(d)))
    return dirs


def installed() -> bool:
    try:
        return all(metadata.version(name) for name in ("nvidia-cublas-cu12", "nvidia-cudnn-cu12"))
    except metadata.PackageNotFoundError:
        return False


def wanted(system: str = sys.platform, gpu_info=None) -> bool:
    """A Windows PC with an NVIDIA card (and its driver) whose libraries are not installed yet."""
    if system != "win32" or os.environ.get("DUBBER_DEVICE", "auto") == "cpu" or installed():
        return False
    from .clone import gpu_info as nvidia_card

    return (gpu_info or nvidia_card)() is not None


class Installer:
    """pip-installs NVIDIA's libraries in the background; a failure only goes to the log (the processor still works)."""

    def __init__(self, log_file: Path, python: str = sys.executable, run=subprocess.run):
        self.log_file, self.python, self.run = log_file, python, run
        self.done = threading.Event()
        self.ok = False

    def command(self) -> list[str]:
        return [self.python, "-m", "pip", "install", "--disable-pip-version-check", *PACKAGES]

    def start(self) -> Installer:
        threading.Thread(target=self.install, daemon=True, name="gpu-install").start()
        return self

    def install(self) -> bool:
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with self.log_file.open("a", encoding="utf-8") as out:
                out.write(f"\n== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(self.command()[1:])}\n")
                out.flush()
                result = self.run(self.command(), stdout=out, stderr=subprocess.STDOUT)
            self.ok = result.returncode == 0
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("Installing NVIDIA's libraries failed: %s", exc)
        if self.ok:
            use_dll_dirs()
            from . import transcribe

            transcribe._gpu_failed = False  # the card may be tried again from the next dub on
            print("Видеокарта NVIDIA готова: распознавание речи пойдёт быстрее.", flush=True)
        else:
            print(f"Не удалось подготовить видеокарту (подробности: {self.log_file}). Речь распознаётся на "
                  "процессоре — это работает, только медленнее.", flush=True)
        self.done.set()
        return self.ok
