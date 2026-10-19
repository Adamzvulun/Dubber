---
id: 14
status: doing
priority: High
blocked_by: []
tags: [translation, claude, settings, web]
---

# Claude translation from the website (key, model, glossary)

Adam: "lets implement the claude key"; key in website settings, default Opus 5.5, general glossary now.
Design: ADR-017. PR: `feat/claude-translation`.

## Narrative
- 2026-10-17: Built and verified offline (unit tests, Chromium, real SDK with a dummy key). Waiting for Adam's review
  and a first real dub with his key (then compare timing with the free path and calibrate chars/second). (by @claude)
- 2026-10-18: Adam set a key and used Opus: "still off sometimes" → prompt v2 + transcription fixes (ADR-021). (by @claude)
- 2026-10-19: Still open: a real dub with a Claude key (quality, cost in `meta.json`); the README guides now explain the setup step by step. (by @claude)
