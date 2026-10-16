---
id: 8
status: doing
priority: High
blocked_by: []
tags: [m3.5, timing, quality]
---

# Dub timing that follows the speaker

Adam: the dub's speed changes don't match the speaker; some sentences rush, others drag.
Research + measurements: `docs/RESEARCH.md` "Dub timing"; steps: `docs/PLAN.md` M3.5.
Free steps implemented (ADR-013); waiting for Adam to re-dub a real video and listen. Paid Claude step deferred.

## Narrative
- 2026-10-16: Measured: Russian Edge speech ≈ 1.47× English, nearly every line at the 1.5× atempo cap, speed jumps
  between lines, Whisper units of 4–11 s cut mid-sentence. Verified Edge `rate` gives exact, predictable durations.
  (by @claude)
- 2026-10-16: Implemented sentence lines, steady-pace planner, Edge rate two-pass, silence trim, timing.json.
  Test talk: all lines on time, pace 1.40–1.50×, no stretching. (by @claude)
- 2026-10-16: Adam's re-dub failed with "No audio was received" (Edge random no-audio ~9% + punctuation-only
  lines; 2× requests since the two-pass TTS). Fixed with skips/retries/fallbacks; waiting for his re-try. (by @claude)
