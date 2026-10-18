---
id: 18
status: done
priority: Normal
blocked_by: []
tags: [quality, audio, demucs]
---

# Remove the speaker's voice, keep music and sounds (Demucs)

Adam liked the idea (2026-10-18); off by default, a switch.

## Narrative
- 2026-10-18: Demucs v4 ONNX on CPU (`separate.py`), switch on the website, CLI `--remove-voice`, new job step;
  verified on a test mix and an end-to-end dub; ≈ +5 min per 10-min video (ADR-020). (by @claude)
