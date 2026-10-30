"""Speech recognition on the NVIDIA card (ADR-034): NVIDIA's libraries fetched by the program itself, no clicks.

Whisper (ctranslate2) uses an NVIDIA card when the driver is there, but needs NVIDIA's cuBLAS 12 and cuDNN 9 DLLs,
which neither Python nor the driver brings: without them every dub failed on such a PC ("cublas64_12.dll is not
found", Adam's new PC, 2026-10-29). Now:
- transcribe.py falls back to the processor when the card fails, so a dub never fails for this;
- on a Windows PC with an NVIDIA card, the program installs the two pip packages (about 1 GB, once) in the
  background at start (`Installer`), and `use_dll_dirs()` lets ctranslate2 find their DLLs: recognition then runs on
  the card, several times faster.

Voice removal on the card (ADR-045): Demucs runs with onnxruntime. Its GPU build (`onnxruntime-gpu`, built for CUDA 13
since 1.2x) can't share the program's Python with the normal `onnxruntime` (same module, and every update reinstalls
the normal one), so it goes into its own folder with its CUDA 13 libraries (`ORT_DIR`, ~1.7 GB, once) and
separate.py runs it in a child process that puts that folder first. Any failure there → the processor, as before.
"""

from __future__ import annotations

import functools
import logging
import os
import shutil
import subprocess
import sys
import sysconfig
import threading
import time
from importlib import metadata
from pathlib import Path

log = logging.getLogger(__name__)

PACKAGES = ("nvidia-cublas-cu12", "nvidia-cudnn-cu12>=9,<10")  # what ctranslate2 4.5+ (CUDA 12) loads
ORT_DIR = Path(sys.prefix) / "onnxruntime-gpu"  # onnxruntime-gpu + its CUDA libraries (in the venv: rebuilt with it)
ORT_EXTRAS = ("cuda", "cudnn")  # onnxruntime-gpu's extras that name the NVIDIA wheels it loads
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
    """Whisper's libraries are installed, and voice removal's (or they failed for this onnxruntime version)."""
    try:
        whisper = all(metadata.version(name) for name in ("nvidia-cublas-cu12", "nvidia-cudnn-cu12"))
    except metadata.PackageNotFoundError:
        return False
    return whisper and (ort_ready() or _ort_failed_marker().exists())


def ort_ready(ort_dir: Path | None = None) -> bool:
    """Voice removal can try the card: onnxruntime-gpu is in its folder (and the user didn't ask for the processor)."""
    return os.environ.get("DUBBER_DEVICE", "auto") != "cpu" and ((ort_dir or ORT_DIR) / "onnxruntime" / "capi").is_dir()


def _ort_version() -> str:
    try:
        return metadata.version("onnxruntime")
    except metadata.PackageNotFoundError:
        return ""


def _ort_failed_marker(ort_dir: Path | None = None) -> Path:
    """Written when installing onnxruntime-gpu failed: not tried again at every start until onnxruntime changes."""
    return (ort_dir or ORT_DIR).with_name(f"onnxruntime-gpu-failed-{_ort_version()}")


def ort_requirements(dist_dir: Path) -> list[str]:
    """The NVIDIA wheels onnxruntime-gpu names in its "cuda"/"cudnn" extras (read from its installed METADATA)."""
    found = []
    for meta in dist_dir.glob("onnxruntime_gpu-*.dist-info/METADATA"):
        for line in meta.read_text(encoding="utf-8").splitlines():
            if line.startswith("Requires-Dist:") and any(f'extra == "{e}"' in line for e in ORT_EXTRAS):
                found.append(line.split(":", 1)[1].split(";")[0].strip())
    return found


@functools.cache
def has_card() -> bool:
    """An NVIDIA card with its driver (nvidia-smi answers); asked once per run of the program."""
    if os.environ.get("DUBBER_DEVICE", "auto") == "cpu":
        return False
    from .clone import gpu_info

    return gpu_info() is not None


def wanted(system: str = sys.platform, gpu_info=None) -> bool:
    """A Windows PC with an NVIDIA card (and its driver) whose libraries are not installed yet."""
    if system != "win32" or os.environ.get("DUBBER_DEVICE", "auto") == "cpu" or installed():
        return False
    from .clone import gpu_info as nvidia_card

    return (gpu_info or nvidia_card)() is not None


class Installer:
    """pip-installs NVIDIA's libraries in the background; a failure only goes to the log (the processor still works)."""

    def __init__(self, log_file: Path, python: str = sys.executable, run=subprocess.run, ort_dir: Path | None = None):
        self.log_file, self.python, self.run = log_file, python, run
        self.ort_dir = ort_dir or ORT_DIR
        self.done = threading.Event()
        self.ok = False
        self.ort_ok = False

    def command(self, *args: str) -> list[str]:
        return [self.python, "-m", "pip", "install", "--disable-pip-version-check", *(args or PACKAGES)]

    def _pip(self, *args: str) -> bool:
        with self.log_file.open("a", encoding="utf-8") as out:
            out.write(f"\n== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(self.command(*args)[1:])}\n")
            out.flush()
            return self.run(self.command(*args), stdout=out, stderr=subprocess.STDOUT).returncode == 0

    def install_ort(self) -> bool:
        """onnxruntime-gpu (the same version as onnxruntime) and its CUDA libraries into `ort_dir`, all or nothing."""
        partial = self.ort_dir.with_name(self.ort_dir.name + ".partial")
        shutil.rmtree(partial, ignore_errors=True)
        ok = self._pip("--target", str(partial), "--no-deps", f"onnxruntime-gpu=={_ort_version()}")
        needs = ort_requirements(partial) if ok else []
        ok = ok and bool(needs) and self._pip("--target", str(partial), *needs)
        if ok:
            shutil.rmtree(self.ort_dir, ignore_errors=True)
            partial.rename(self.ort_dir)
        else:
            shutil.rmtree(partial, ignore_errors=True)
            _ort_failed_marker(self.ort_dir).write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        return ok

    def start(self) -> Installer:
        threading.Thread(target=self.install, daemon=True, name="gpu-install").start()
        return self

    def install(self) -> bool:
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.ok = self._pip()
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
        if not ort_ready(self.ort_dir) and _ort_version():
            try:
                self.ort_ok = self.install_ort()
            except (OSError, subprocess.SubprocessError) as exc:
                log.warning("Installing onnxruntime-gpu failed: %s", exc)
            print("Видеокарта NVIDIA готова и для отделения голоса — оно пойдёт быстрее." if self.ort_ok else
                  f"Отделение голоса остаётся на процессоре (подробности: {self.log_file}).", flush=True)
        self.done.set()
        return self.ok
