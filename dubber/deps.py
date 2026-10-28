"""Checks that every component the program needs is installed and loads. The Windows launcher runs it at every start.

    python -m dubber.deps   exit 0: all fine
                            exit 1: components missing or too old (printed; `pip install -e .` repairs it)
                            exit 2: installed, but their native code does not load (printed; on Windows almost always
                                    the Microsoft Visual C++ runtime missing or too old)

Catches what a first install can leave behind: an interrupted install or update, a component the antivirus removed,
a fresh PC without the C++ runtime (onnxruntime and ctranslate2 need msvcp140.dll, which Python doesn't bring).
"""

from __future__ import annotations

import importlib
import re
import sys
from importlib import metadata
from pathlib import Path

from .config import PROJECT_ROOT

# Components with native code (DLLs) that must load: Whisper (ctranslate2, av), the offline translator and voice
# removal (onnxruntime).
NATIVE = ("ctranslate2", "av", "onnxruntime", "tokenizers", "numpy")

_DEPENDENCIES = re.compile(r"^dependencies\s*=\s*\[(.*?)^\]", re.M | re.S)
_REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(?:\[[^\]]*\])?\s*(?:>=\s*([0-9][0-9.]*))?")


def requirements(pyproject: Path = PROJECT_ROOT / "pyproject.toml") -> list[tuple[str, str | None]]:
    """(name, minimum version or None) for each entry of `[project] dependencies`."""
    block = _DEPENDENCIES.search(pyproject.read_text(encoding="utf-8"))
    out = []
    for entry in re.findall(r'"([^"]+)"', block.group(1) if block else ""):
        match = _REQUIREMENT.match(entry)
        if match:
            out.append((match.group(1), match.group(2)))
    return out


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3])


def missing(reqs: list[tuple[str, str | None]] | None = None) -> list[str]:
    """Components not installed, or older than the program asks for ("name>=version")."""
    out = []
    for name, minimum in requirements() if reqs is None else reqs:
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            out.append(name)
            continue
        if minimum and _version(installed) < _version(minimum):
            out.append(f"{name}>={minimum} (installed {installed})")
    return out


def broken(modules: tuple[str, ...] = NATIVE) -> list[str]:
    """Modules that are installed but fail to load ("module: error")."""
    out = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # ImportError "DLL load failed", OSError [WinError 126], ...
            out.append(f"{name}: {exc}".splitlines()[0])
    return out


def main() -> int:
    if gone := missing():
        print(", ".join(gone))
        return 1
    if failed := broken():
        print("; ".join(failed))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
