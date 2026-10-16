#!/bin/bash
# Cloud-session setup: install Dubber's Python deps so `ruff check .` and `pytest` work.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

if ! command -v ffmpeg >/dev/null 2>&1; then
  (apt-get update -qq && apt-get install -y -qq ffmpeg) || echo "warning: could not install ffmpeg" >&2
fi

[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -e ".[dev]"

echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
