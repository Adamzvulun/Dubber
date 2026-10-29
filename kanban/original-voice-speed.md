---
id: 36
status: review
priority: High
blocked_by: []
tags: [nvidia, original-voice, qa, v0.10.2, v0.10.3]
---

# «Оригинал» slow on the RTX 5060 Ti; install progress bar; QA pass

Adam (2026-10-29): a 5-min «Оригинал» dub estimated 90 min with the GPU looking idle; asked for a progress bar for the
voice studio install, whether the background switches should be on with «Оригинал», and QA agents on the site.

## Narrative
- 2026-10-29: 0.10.2 (ADR-035): card check + no CPU crawl, device/timing lines, `tts_clone` ETA, voice-free background
  with «Оригинал», install progress bar; phone QA fixes. Waiting for Adam's numbers from the real card. (by @claude)
- 2026-10-29: PR #17 open. Next: Adam's numbers from the RTX 5060 Ti (see STATUS "Next steps" 0). (by @claude)
- 2026-10-29: 0.10.2 merged; Adam: card used (~50%), words swallowed/warped. 0.10.3 (ADR-036): speed floor per
  line, bigger length-sorted groups. Next: Adam re-dubs the same video and reports. (by @claude)
