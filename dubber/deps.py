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
# removal (onnxruntime), who says each line (sherpa_onnx).
NATIVE = ("ctranslate2", "av", "onnxruntime", "tokenizers", "numpy", "sherpa_onnx")

_DEPENDENCIES = re.compile(r"^dependencies\s*=\s*\[(.*?)^\]", re.M | re.S)
_REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(?:\[([^\]]*)\])?\s*(?:>=\s*([0-9][0-9.]*))?")


def requirements(pyproject: Path = PROJECT_ROOT / "pyproject.toml") -> list[tuple[str, str | None]]:
    """(name, minimum version or None) for each entry of `[project] dependencies`."""
    return [(name, minimum) for name, _extras, minimum in _entries(pyproject)]


def _entries(pyproject: Path = PROJECT_ROOT / "pyproject.toml") -> list[tuple[str, list[str], str | None]]:
    block = _DEPENDENCIES.search(pyproject.read_text(encoding="utf-8"))
    out = []
    for line in (block.group(1) if block else "").splitlines():
        line = line.split("#", 1)[0]  # comments may quote words
        for entry in re.findall(r'"([^"]+)"', line):
            match = _REQUIREMENT.match(entry)
            if match:
                extras = [e.strip() for e in (match.group(2) or "").split(",") if e.strip()]
                out.append((match.group(1), extras, match.group(3)))
    return out


def extra_components(pyproject: Path = PROJECT_ROOT / "pyproject.toml") -> list[str]:
    """Packages that the extras we ask for pull in (e.g. curl_cffi from yt-dlp[curl-cffi]): `missing()` checks
    them too — a plain `pip install --upgrade yt-dlp` would not have installed them."""
    try:
        from packaging.requirements import Requirement
    except ImportError:
        return []
    out = []
    for name, extras, _minimum in _entries(pyproject):
        try:
            requires = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            continue  # reported by missing() already
        for spec in requires:
            req = Requirement(spec)
            if req.marker and any(req.marker.evaluate({"extra": e}) for e in extras) \
                    and not req.marker.evaluate({"extra": ""}):
                out.append(req.name)
    return sorted(set(out))


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3])


def missing(reqs: list[tuple[str, str | None]] | None = None) -> list[str]:
    """Components not installed, or older than the program asks for ("name>=version")."""
    if reqs is None:
        reqs = requirements() + [(name, None) for name in extra_components()]
    out = []
    for name, minimum in reqs:
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
