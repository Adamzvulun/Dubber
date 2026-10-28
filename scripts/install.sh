#!/usr/bin/env bash
# Install Dubber on macOS / Linux. Needs Python 3.10-3.14 and ffmpeg.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo "Please install ffmpeg first (macOS: brew install ffmpeg; Ubuntu: sudo apt install ffmpeg)"; exit 1; }
# Python 3.10-3.14 only: a newer one (3.15, October 2026) has no onnxruntime build yet -> "No matching distribution".
supported() { "$1" -c 'import sys; sys.exit(not (3, 10) <= sys.version_info[:2] <= (3, 14))' 2>/dev/null; }
if [ -x .venv/bin/python ] && ! supported .venv/bin/python; then rm -rf .venv; fi
if [ ! -d .venv ]; then
  PY=""
  for c in python3.12 python3.13 python3.11 python3.14 python3.10 python3; do
    if command -v "$c" >/dev/null && supported "$c"; then PY="$c"; break; fi
  done
  [ -n "$PY" ] || { echo "Please install Python 3.12 (3.10-3.14 work; newer ones are not supported yet)"; exit 1; }
  "$PY" -m venv .venv
fi
rm -f install.log  # full pip log, to share if something goes wrong
# Build tools in .venv, no pip build isolation (a silent extra step that could stall after "Obtaining file://...").
.venv/bin/python -m pip install --upgrade pip setuptools wheel --log install.log >/dev/null
.venv/bin/python -m pip install --upgrade --no-build-isolation --log install.log -e .
.venv/bin/python -m pip install --upgrade 'yt-dlp[default,curl-cffi]' --log install.log >/dev/null
echo "Installed. Start with ./scripts/start.sh"
