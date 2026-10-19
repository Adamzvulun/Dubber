---
id: 26
status: done
priority: High
blocked_by: []
tags: [windows, install]
---

# Readable Russian in the window; shortcut after a self-update (v0.6.1)

Adam's screenshot (2026-10-18): window title right, every Russian line `?`; and after the self-update to 0.6.0 no
desktop shortcut until «Start Dubber» ran.

## Narrative
- 2026-10-18: Raster console font → Consolas in `dubber.ps1`; the program runs `dubber.ps1 -ShortcutOnly` when started
  without the launcher (ADR-025 follow-up). Windows CI checks the shortcut path; the font can only be checked on
  Adam's screen — waiting for his confirmation. (by @claude)
