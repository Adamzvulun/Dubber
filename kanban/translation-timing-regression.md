---
id: 11
status: doing
priority: High
blocked_by: []
tags: [quality, timing, translation, bug]
---

# Translation quality and timing worse than before the language work

Adam (2026-10-17, session 2): the EN+FR video now works, "but the quality of the translation went down and the
timing is not as good as it was before". Timing code (`timing.py`, `align.py`) is unchanged since ADR-013, so the
difference must come from the lines it gets. Candidates (to prove, not assume):
1. His dub used the offline NLLB backup (Google refused) — literal, longer lines → worse wording and faster voice.
   Check `"translator"` in `output/<id>/meta.json`.
2. Google path changed: deep-translator (translate.google.com, 60 lines / 4000 chars per call) → `client=gtx` JSON
   endpoint (40 lines / 1500 chars, explicit source language). Less context per call; possibly a different model.
3. Transcription changed for mixed videos: each language run is transcribed alone (less context, cut at run edges),
   lines split at every language change → shorter, choppier lines.
Evidence needed from Adam's PC, `work/<id>/` (old and new caches side by side): `segments_en_v2.json`,
`segments_ru_v2.json`, `timing_v3_*.json` (old) vs `segments_src_v3.json`, `segments_ru_v3.json(.translator)`,
`timing_ru-RU-*_*.json` (new), plus `speech_info.json` and `output/<id>/meta.json`.

## Narrative
- 2026-10-17: Created from Adam's report; hypotheses from a code diff 3e4955f..HEAD. Waiting for his files. (by @claude)
