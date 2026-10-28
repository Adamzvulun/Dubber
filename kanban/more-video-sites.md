---
id: 32
status: review
priority: Normal
blocked_by: [Adam: test real links]
tags: [future, download]
---

# Dub videos from Facebook, Instagram and TikTok

Adam (2026-10-28): add support for dubbing videos from Facebook / Instagram / TikTok links. Later — not started.

Notes: yt-dlp already has extractors for all three; many posts need a logged-in session (cookies from the user's
browser), short vertical videos need the player/thumbnail layout checked, and the link check in the form
(`dubber/app.py`, `dubber/web/app.js`) currently expects YouTube or a file.

## Narrative
- 2026-10-28: Card created at Adam's request as future work. (by @claude)
- 2026-10-28: Built (v0.9.0, ADR-031): any of the three links works like a YouTube one; logins via a cookies file in Settings → «Вход на сайты» (Adam's choice; Chrome/Edge guide); HEVC → H.264. Waiting for Adam to try real links. (by @claude)
