---
id: 31
status: review
priority: Normal
blocked_by: []
tags: [future, mobile]
---

# Phone version: fully usable on iPhone and Samsung (Android) — v0.10.0, ADR-033

Adam (2026-10-28): port the app to phones and make it fully usable on iPhone / Samsung. Later — not started.

Open questions for the brainstorm: where the dubbing runs (the phone can't run Whisper/Demucs well — a home PC
reached from the phone, a hosted server (see `kanban/hosting-hf-spaces.md`), or a mix); installable web app (PWA)
vs. native app; how the phone reaches the PC outside the home network; playback, downloads and subtitles on iOS
Safari (the on-screen subtitles are native text tracks, so they already show in iOS full screen).

## Narrative
- 2026-10-28: Card created at Adam's request as future work. (by @claude)
- 2026-10-28: Brainstorm with Adam: same flow as on the PC; anywhere; dub at once or queue while the PC is off
  (send-and-forget); home-screen icon; one-click install, no accounts for users. Built 0.10.0: Cloudflare quick
  tunnel + mailbox Worker + the same website as a PWA (ADR-033), PR #15. Next: Adam's Cloudflare account + secrets,
  `phone.MAILBOX_URL`, then a real Samsung/iPhone test. (by @claude)
