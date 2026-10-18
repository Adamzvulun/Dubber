---
id: 23
status: done
priority: High
blocked_by: []
tags: [install, windows]
---

# One-click Windows start with a desktop shortcut and icon

Adam (2026-10-18): the installer still printed question marks and created no shortcut; one icon should install, create a desktop shortcut with its own logo, and start.

## Narrative
- 2026-10-18: `Start Dubber.cmd` → `scripts/windows/dubber.ps1` (UTF-8 BOM), IShellLinkW shortcut + `dubber/assets/dubber.ico`; bug reproduced and fixed in the new Windows CI job (ADR-025). (by @claude)
