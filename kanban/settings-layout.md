---
id: 34
status: done
priority: High
blocked_by: []
tags: [ui, settings]
---

# Settings page squeezed on a PC — reverted, one column kept

Adam (2026-10-28, session 8): "the settings window was squeezed — fix that and make sure it's ok on PC".
Cause: the panels sat in a 760 px column on the left of the 1120 px page, leaving the right half empty.
Fix: two columns from 1000 px (`.settings__col`), one column below with «Место на диске» last; site tiles 4 or 2×2
(container query).

## Narrative
- 2026-10-28: Reproduced in Chromium on the stub server (1920/1366/1280 px), fixed, checked 1920/1366/1280/1024/900/
  600/360 px, RU/EN, light/dark: no horizontal scroll, tiles never 3+1. (by @claude)
- 2026-10-28: Adam: no two columns — keep the single column as in #12/#13/#14 (760 px, unchanged since). Reverted;
  no release. (by @claude)
