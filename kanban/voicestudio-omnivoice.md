---
id: 30
status: doing
priority: High
blocked_by: [Adam: test on the RTX 3070 PC]
tags: [research, quality, voice]
---

# Research: VoiceStudio / OmniVoice (voice cloning) for better dubs

Adam (2026-10-19): research https://github.com/debpalash/voicestudio — use it or replace parts of Dubber with it to
improve the dub. Findings: `docs/RESEARCH.md` → "VoiceStudio / OmniVoice"; proposal ADR-028.

## Narrative
- 2026-10-19: Read the repo; measured OmniVoice on 4 CPU cores: ≈ 20× slower than real time (2 h per 10-min video),
  Russian clear, Hebrew garbled (13 h of Hebrew training data). Useful only with an NVIDIA GPU. Borrowable without it:
  listen-back check of the dub, slight video slow-down instead of rushed speech, a voice per speaker. Asked Adam
  about his GPU and which idea to build. (by @claude)
- 2026-10-19: Adam: father's PC has an RTX 3070 + i7-11700 → build an opt-in «Оригинал» voice with a GPU warning.
  Chose: each speaker's own voice (per-line references from the Demucs vocals), Edge for Hebrew, install from
  Settings. Built `dubber/clone.py` + pipeline/app/UI (v0.7.0, ADR-028); verified with stand-ins, in Chromium and with a
  real CPU dub; waiting for the first run on the 3070. (by @claude)
