---
id: 10
status: todo
priority: High
blocked_by: []
tags: [handoff, next]
---

# Next steps (hand-off at the end of session 9, 2026-10-30)

Read `docs/STATUS.md` first (its "Next steps" has the details). `main` = v0.11.0; 0.12.0 (session 10: library card
per dub, foreign lines, the accent fix) is a PR from `claude/happy-brahmagupta-3zznvd`. Open items, in order:
00. **Adam merges 0.12.1** (PR #23: accent fix out). Then QA leftovers (`kanban/nice-to-haves.md`), as Adam asked.
0. **Adam re-dubs with 0.11.0 and listens** — speakers, one voice per person, soft edges, overlaps; ask for the window
   lines + `timing.json` + `clips_original_ru/check.json` (`kanban/original-voice-quality.md`).
1. **Asked by Adam for next (not started):** one library card per dub (`kanban/library-card-per-dub.md`); «Оригинал»
   weak points + the American accent in Russian (`kanban/original-voice-quality.md`).
2. **Switch the phone version on** (`kanban/phone-app.md`, ADR-033): Adam's Cloudflare account + 2 GitHub secrets
   + the workers.dev address → set `phone.MAILBOX_URL` (small PR) → deploy → pair his Samsung.
3. **Real TikTok / Instagram / Facebook links without a login** — ask what failed; login window only if asked.
4. **Father's Windows 11 PC:** fresh install + both subtitle switches (`kanban/install-and-subtitles.md`).
5. QA leftovers and ideas: `kanban/nice-to-haves.md` (offer, don't build unasked).

## Narrative
- 2026-10-17: Created at the end of session 1 as the hand-off list. (by @claude)
- 2026-10-18: Rewritten at the end of session 2. (by @claude)
- 2026-10-19: Rewritten at the end of session 5 (0.6.1 shipped, README guides RU + HE). (by @claude)
- 2026-10-28: Rewritten at the end of session 7 (0.8.0 merged; 0.9.0 = PR #14 with TikTok/Instagram/Facebook). (by @claude)
- 2026-10-28: Session 8: 0.9.0 merged; 0.9.1 settings layout; phone brainstorm started. (by @claude)
- 2026-10-29: Rewritten at the end of session 8 (0.10.0 phone, 0.10.1 NVIDIA merged; 0.10.2 = PR #17). (by @claude)
- 2026-10-29: Session 9: 0.10.2 merged; 0.10.3 for Adam's «Оригинал» findings. (by @claude)
- 2026-10-29: Session 9b: 0.10.3 merged; 0.10.4 listen-back + names. (by @claude)
- 2026-10-29: Session 9c: 0.10.4 merged; 0.11.0 speakers + library times. (by @claude)
- 2026-10-30: Rewritten at the end of session 9 (0.10.3–0.11.0 merged; Adam's next asks). (by @claude)
- 2026-10-30: Session 10: 0.12.0 built (ADR-041…043), PR for Adam. (by @claude)
