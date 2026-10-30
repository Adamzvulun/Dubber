---
id: 37
status: done
priority: High
blocked_by: []
tags: [library, ui, next]
---

# One library card per dub

Adam (2026-10-30): "separate card for each dub in the library". Since 0.11.0 every dub run is already its own entry
with its date and time (ADR-039: `output/<video>--<lang>-<hash>-<YYYYMMDD-HHMMSS>/`), but the library still groups a
video's dubs on one card (ADR-027, his choice on 2026-10-18; `videoGroups()` + the card builder in
`dubber/web/app.js`). Now: one card per dub, newest first.

## To do
- Library: drop the grouping — each dub its own card (thumbnail, title, language · voice · sound, date + time).
- Keep the search (title/channel) and the "Recent videos" strip on the home page consistent with it.
- Watch page: keep «Другие озвучки этого видео» (with dates + times) — ask Adam only if unsure.
- Check the phone mode (`/p/<token>/`), RU/EN, 360/1280 px, dark; update the RU/HE guides in `README.md` (they say
  "one card per video") and `docs/README.ru.md`; a new ADR superseding ADR-027's grouping; version + changelog.

## Narrative
- 2026-10-30: Created from Adam's hand-off request at the end of session 9 (not started). (by @claude)
- 2026-10-30: Built (ADR-041): one card per dub newest first, count in dubs, tag row removed; other dubs kept on the
  watch page; guides RU/HE + README.ru updated; Chromium RU/EN 1280/360 dark checked. (by @claude)
