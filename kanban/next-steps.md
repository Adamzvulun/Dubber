---
id: 10
status: todo
priority: High
blocked_by: []
tags: [handoff, next]
---

# Next steps (hand-off at the end of session 3)

Read `docs/STATUS.md` first. Open items, in order:
1. Adam reviews and merges **PR #6** (v0.4.0, branch `claude/dubber-project-continuation-6ukr86`) and updates his PC
   (close the window → extract `main` over the folder → `install_windows.bat`). Footer must say 0.4.0. If CI or
   review asks for changes, fix them on that same branch.
2. Adam listens (ask for his impressions; files via an `uploads/…` branch if something is wrong):
   - a **Hebrew** dub with Claude — does pronunciation feel better now that Claude spells for the voice
     (`kanban/hebrew-voice.md`, ADR-019)?
   - an **English** dub with Claude — translation quality after prompt v2 (the first run re-translates once; check
     `meta.json` `translation_cost_usd`) (ADR-021);
   - one dub with **«Убрать голос диктора»** — voice gone, music kept, how long it took (ADR-020).
3. If Hebrew misspellings come from the free path too (Google/offline), add a spelling fix there (PLAN M7).
4. Offer product ideas: several dub languages of one video in the library; upload a local file from the website;
   voice speed control; a queue (PLAN M3/M4).
5. Still unconfirmed from earlier: H.264 playback in Chrome/Edge, the desktop shortcut.

## Narrative
- 2026-10-17: Created at the end of session 1 as the hand-off list. (by @claude)
- 2026-10-18: Rewritten at the end of session 2. (by @claude)
- 2026-10-18: Rewritten at the end of session 3 (Hebrew voice measured, transcription fixes, Claude prompt v2,
  voice removal; PR #6). (by @claude)
