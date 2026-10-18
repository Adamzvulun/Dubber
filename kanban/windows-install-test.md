---
id: 7
status: done
priority: High
blocked_by: [3]
tags: [m2, install, verification]
---

# Install and test on a real Windows PC

Adam runs `scripts/install_windows.bat` on a real PC, starts the site, dubs one video and reports:
installer OK? video plays in Chrome/Edge (H.264)? Google translation quality from a home connection?
Steps for Adam are in `docs/STATUS.md` / `README.md`; the user guide is `docs/README.ru.md`.

## Narrative
- 2026-10-16: Created at the end of session 1 — the last unverified pieces all need a real PC. (by @claude)
- 2026-10-16: First run: packages installed OK; desktop shortcut failed (Cyrillic name became `?`). Fixed in the
  installer; waiting for Adam to re-run it and start the site. (by @claude)
- 2026-10-16: Site runs on Windows; first dub failed downloading Whisper via Hugging Face Xet. Switched to plain
  HTTPS + retries; waiting for Adam's next try. (by @claude)
- 2026-10-17: Installed and dubbing on Adam's PC. Follow-ups (re-check fixed shortcut, H.264 in real
  Chrome/Edge) moved to `kanban/next-steps.md`. (by @claude)
