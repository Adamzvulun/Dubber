---
id: 15
status: done
priority: High
blocked_by: []
tags: [bug, install, web, eta]
---

# Updates always visible + time left on the job card

Adam: "I can't see the settings icon nor the model button" after updating to `main`; wants a time-left timer.

## Narrative
- 2026-10-17: Cause: old server still on port 7860 (new start failed, browser showed the old page) + uncached site
  files. Fixed with a start-up check, no-cache, version in the footer (ADR-018). Time left from learned stage shares.
  PR `fix/updates-and-eta`; waiting for Adam to update and confirm the footer says 0.3.0. (by @claude)
- 2026-10-18: Adam updated: old page first, then new page with old styles after refresh. Cause: browsers reuse
  saved CSS/JS on refresh (saved before no-cache existed). Fix v0.3.1: versioned file addresses; clear cached files
  once for this update (Ctrl+F5 didn't help in Opera GX). PR `fix/asset-versions`. (by @claude)
- 2026-10-19: Closed — updates are automatic since 0.5.0 (self-update, ADR-024); the time-left estimate shipped in 0.3.1. (by @claude)
