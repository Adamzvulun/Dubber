#!/usr/bin/env bash
# Install Dubber on macOS / Linux. Needs python3 (3.10+) and ffmpeg.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo "Please install ffmpeg first (macOS: brew install ffmpeg; Ubuntu: sudo apt install ffmpeg)"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
rm -f install.log  # full pip log, to share if something goes wrong
# Build tools in .venv, no pip build isolation (a silent extra step that could stall after "Obtaining file://...").
.venv/bin/python -m pip install --upgrade pip setuptools wheel --log install.log >/dev/null
.venv/bin/python -m pip install --upgrade --no-build-isolation --log install.log -e .
.venv/bin/python -m pip install --upgrade yt-dlp --log install.log >/dev/null
echo "Installed. Start with ./scripts/start.sh"
