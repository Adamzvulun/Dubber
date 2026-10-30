---
id: 36
status: done
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
- 2026-10-29: 0.10.3 merged; Adam: better, still cut off + English words. 0.10.4 (ADR-037): listen-back
  check, ≤1.25×, Claude prompt v3. Next: his re-dub + `check.json`. (by @claude)
- 2026-10-29: 0.10.4 merged; Adam: rough edges, wants speakers/overlap + separate dubs with time. 0.11.0
  (ADR-038/039/040). Next: his ears. (by @claude)
- 2026-10-30: 0.11.0 merged (PR #20). Closed; follow-ups in `kanban/original-voice-quality.md` and
  `kanban/library-card-per-dub.md`. (by @claude)
