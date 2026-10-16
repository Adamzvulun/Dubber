---
id: 8
status: todo
priority: High
blocked_by: []
tags: [m3.5, timing, quality]
---

# Dub timing that follows the speaker

Adam: the dub's speed changes don't match the speaker; some sentences rush, others drag.
Research + measurements: `docs/RESEARCH.md` "Dub timing"; steps: `docs/PLAN.md` M3.5.
Waiting for Adam's go-ahead on the plan (and whether the optional Claude length-budget step is wanted).

## Narrative
- 2026-10-16: Measured: Russian Edge speech ≈ 1.47× English, nearly every line at the 1.5× atempo cap, speed jumps
  between lines, Whisper units of 4–11 s cut mid-sentence. Verified Edge `rate` gives exact, predictable durations.
  (by @claude)
