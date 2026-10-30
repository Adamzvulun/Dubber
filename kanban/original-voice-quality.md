---
id: 38
status: todo
priority: High
blocked_by: []
tags: [original-voice, quality, next]
---

# «Оригинал»: weak points and the American accent

Adam (2026-10-30), after 0.11.0 was merged: "work on improving the weak points you mentioned, also sometimes the
dubbed version, for example Russian, is said with an American accent — not good." First wait for his 0.11.0 re-dub
report (STATUS Next steps 0) — it may change the order.

## Weak points (seen in his `check.json`, 2026-10-29)
1. **One-word lines** ("Да.", "Правда?") come out as babble even after 3 tries (e.g. "Да." heard as
   "РАДОСТНЫЕ ПОЗИТИВАЮЩИЕ"). OmniVoice is weak on very short text. Ideas: speak the word together with the same
   speaker's neighbouring line and cut it out by word timings; or a longer minimum duration; or fall back to the
   last good clip of that speaker saying something similar. Measure on the sandbox CPU first (STATUS gotchas).
2. **Foreign speech inside the original** (Spanish in an English film): Whisper (forced to the video's language)
   mishears it, Claude (prompt v3: "spell as pronounced") transliterates nonsense — "Йо, хани, че, хайста,
   компстрайб." Ideas: let the language detector's per-region language reach Whisper for short runs; tell Claude to
   translate the meaning when a line looks like misheard foreign speech, or mark it untranslatable and leave the
   original audio there.
3. **True crosstalk** (two people at the same moment): Whisper writes only the louder one, so only it is dubbed.
   Needs separating the voices first (speech separation) — big; offer, don't build unasked.

## The American accent
The copied voice keeps the reference's accent: the reference is the speaker's own English speech, and OmniVoice
copies timbre *and* accent (cross-lingual cloning). Possibly also Latin-letter words read in English (prompt v3 should
have removed most). Candidate approaches — research and measure before proposing to Adam:
- **Edge Russian voice + voice conversion** (e.g. OpenVoice v2 tone-color converter, MIT; Seed-VC): native Russian
  pronunciation from Edge, the speaker's timbre converted on top. Check licence, size, GPU/CPU speed, quality.
- OmniVoice options: its `instruct` is for voice design, not cloning — check whether any generation setting reduces
  accent transfer; shorter references; a reference passed through a neutral voice first.
- How to judge: Whisper's read-back can't hear accent — compare with a native Russian TTS by ear on samples Adam
  rates, or a language-ID score on the clips.

## Narrative
- 2026-10-30: Created from Adam's hand-off request at the end of session 9 (not started). (by @claude)
- 2026-10-30: Weak point 2 (foreign lines): reproduced with Edge voices under noise; second-opinion language check
  + Claude prompt v4 (ADR-042). Accent: measuring OmniVoice with a voice-converted Russian reference. (by @claude)
- 2026-10-30: Accent: Adam chose (b); built in 0.12.0 (ADR-043). One-word lines: fine with a clean reference at the
  current floor (1 seed) — next: look at the reference of his babbled lines. (by @claude)
