---
id: 2
status: done
priority: High
blocked_by: [1]
tags: [m1, pipeline]
---

# Dubbing pipeline + CLI

download → transcribe → translate → tts → align → mux → subtitles, cached per video; unit + e2e tests.

## Narrative
- 2026-10-16: Card created during session 1 planning. (by @claude)
- 2026-10-16: Code + 18 offline tests done. Real end-to-end run still pending: the cloud sandbox blocks YouTube, Bing TTS, Google Translate and Hugging Face. (by @claude)
- 2026-10-16: Real end-to-end test passed on two TED-Ed videos (CLI + web UI). Found and fixed 4 real bugs (PyAV/Whisper crash, offline translator dropping sentences, re-download on retry, TTS proxy) plus deno + cookies needs. Verified by ffprobe and by Whisper listening to the Russian track. (by @claude)
