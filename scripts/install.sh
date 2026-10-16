#!/usr/bin/env bash
# Install Dubber on macOS / Linux. Needs python3 (3.10+) and ffmpeg.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo "Please install ffmpeg first (macOS: brew install ffmpeg; Ubuntu: sudo apt install ffmpeg)"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install --upgrade -e .
.venv/bin/python -m pip install --upgrade yt-dlp >/dev/null
echo "Installed. Start with ./scripts/start.sh"
