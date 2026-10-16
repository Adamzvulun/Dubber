---
id: 2
status: doing
priority: High
blocked_by: [1]
tags: [m1, pipeline]
---

# Dubbing pipeline + CLI

download → transcribe → translate → tts → align → mux → subtitles, cached per video; unit + e2e tests.

## Narrative
- 2026-10-16: Card created during session 1 planning. (by @claude)
- 2026-10-16: Code + 18 offline tests done. Real end-to-end run still pending: the cloud sandbox blocks YouTube, Bing TTS, Google Translate and Hugging Face. (by @claude)
