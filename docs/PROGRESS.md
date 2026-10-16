# Progress log

Newest entries at the top. One entry per working session / milestone.

## 2026-10-16 — Session 1: research, skills, foundation
- Agreed scope with Adam: runs on father's PC, free-first, outputs = dubbed MP4 + RU subtitles + transcript.
- Researched existing dubbing projects and building blocks → `docs/RESEARCH.md`.
- Searched GitHub for Claude skills; cloned 11 repos, reviewed code, installed 12 skills → `docs/SKILLS.md`.
  Removed one auto-installing script from `youtube-downloader`; skipped two unlicensed skills.
- Wrote `CLAUDE.md`, plan, decisions, kanban board.
- M1: implemented the pipeline (`dubber/`): download, transcribe, translate (Google/Claude), tts, align, mux,
  subtitles, cached `pipeline.run`, CLI. 18 tests pass (`ruff` clean); offline e2e test builds a real MP4
  with 2 audio tracks + RU subtitles from a synthetic video using stubbed network services.
- **Blocked in the cloud sandbox:** network policy denies www.youtube.com, speech.platform.bing.com (edge-tts),
  translate.google.com, huggingface.co (Whisper models). Real end-to-end run pending (allow these domains or run on a PC).
- M2: Russian web UI (`dubber/app.py`, Gradio 6): link box, voice choice, live progress in Russian, video player
  with subtitles, 4 download buttons, history of earlier videos, Russian error messages. Verified in headless
  Chromium via Playwright (validation, full run, downloads visible, phone width, no console errors). Error popups
  show "Ошибка" on a Russian-locale browser. The headless test browser can't play H.264, so in-page playback was not
  verified here (normal Chrome/Edge play it).
- Installers: `scripts/install_windows.bat` (winget Python + ffmpeg, venv, desktop shortcut), `start_windows.bat`,
  `install.sh` / `start.sh`. Not yet tried on a real Windows PC.
- SessionStart hook (`.claude/hooks/session-start.sh`) installs deps in cloud sessions. 21 tests pass.
- Claude translation defaults to `claude-opus-5-5` (effort low, structured JSON output, server-side refusal fallback).
