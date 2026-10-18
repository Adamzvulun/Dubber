---
id: 17
status: done
priority: High
blocked_by: []
tags: [quality, tts, hebrew]
---

# Hebrew dub mispronounces words

Adam (2026-10-18): wrong stress and syllables, e.g. "the rest" read "iter" instead of "yeter". Free only.

## Narrative
- 2026-10-18: Measured 5 free options on 50 gold sentences (`tools/qa_hebrew_voice.py`): plain Edge best; niqqud
  makes Edge worse; the "iter" comes from the spelling ייתר. Kept Edge, added Hebrew/Russian spelling notes to the
  Claude prompt (ADR-019). Waiting for Adam to listen to a v0.4.0 Hebrew dub. (by @claude)
