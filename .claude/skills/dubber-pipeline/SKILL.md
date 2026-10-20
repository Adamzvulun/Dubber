---
name: dubber-pipeline
description: How the Dubber dubbing pipeline (any spoken language → 12 dub languages, Russian default) works and how to run, debug or extend a stage (download, transcribe, translate, tts, align, mux). Use whenever touching code in dubber/ or investigating a bad dub (wrong timing, missing audio, translation problems, download failures).
---

# Dubber pipeline

`dubber/pipeline.py::run(source, settings, progress, translator=, synth=, transcriber=)` runs:

| # | Stage | Module | Cache file in `work/<video-id>/` |
|---|---|---|---|
| 1 | Download (yt-dlp or local copy) | `download.py` | `source.mp4` |
| 2 | Transcribe any language: language per stretch of speech (`language_runs`), each run in its own language, word timestamps → sentence lines (`split_into_units`) | `transcribe.py`, `segments.py` | `audio_16k.wav`, `segments_src_v3.json` (with `lang` per line), `speech_info.json` |
| 3 | Translate → target language: one-language batches, Google (retries) / Claude, NLLB-200 offline backup, quality gate (`Translator`) | `translate.py` | `segments_<lang>_v3.json` (+ `.translator`) |
| 4 | TTS twice: natural speed (measure) → `timing.plan_rates` → planned Edge `rate` | `tts.py`, `timing.py` | `clips_<voice>/00000_<texthash>[_+35].mp3` (per voice) |
| 5 | Trim clip silence, place lines at their start, ≤1.1× atempo correction, build track | `align.py` | `dub_track_<voice>_<hash>.wav`, `timing_<voice>_<hash>.json` |
| 6 | Subtitles + final MP4 | `subtitles.py`, `mux.py` | `output/<id>/` (dubbed.mp4, meta.json with `target_lang`/`source_lang(s)`/`files`, thumbnail.jpg, segments.json, `subtitles_<lang>/src.*`, `transcript_<lang>.txt`, `transcript_src_<lang>.txt`) |

Optional stages: **voice removal** (`separate.py`, Demucs ONNX → `background_htdemucs.wav`, before the mux) and the
**original voice** (`clone.py`, voice `"original"`, OmniVoice on an NVIDIA GPU, installed from Settings): the voice is
split off *before* TTS (`vocals_htdemucs.wav` → `vocals_24k.f32`), each line copies whoever said it, clips in
`clips_original_<lang>/`; Hebrew, not installed or any error → the Edge male voice + `voice_notes` in meta.json (ADR-028).

**Resume/cache rule:** a stage is skipped if its cache file exists. To redo a stage, delete its file
and everything after it (e.g. new translation → delete `segments_<lang>_v3.json`; the track is keyed by the lines' content, clips by their text).
`Segment.ru` holds the translation in whatever the dub language is (name kept for compatibility).

## Running
```bash
.venv/bin/python -m dubber.cli "https://www.youtube.com/watch?v=..."   # or a local .mp4
.venv/bin/python -m dubber.app                                          # website (FastAPI + dubber/web/)
DUBBER_WHISPER_MODEL=tiny  DUBBER_TRANSLATOR=google  DUBBER_VOICE=ru-RU-SvetlanaNeural  # env knobs (see config.py)
```

## Debugging checklist
- **Download fails (403 / "confirm you're not a bot")** → `pip install -U yt-dlp` first; then see the
  `youtube-downloader` skill references (cookies, PO tokens). Cloud/datacenter IPs are often blocked.
- **Dub doesn't follow the speaker (rushing / dragging / late)** → read `output/<id>/timing.json`: `median_rate`
  (voice pace), `late_lines`/`max_delay` (lines pushed back), `stretched_lines` (needed atempo). Pace rules live in
  `timing.py` (BAND, STEP, BREATH); `DUBBER_MAX_SPEEDUP` caps the voice rate. Edge clips carry ~0.25 s + ~0.9 s of
  silence — always measure with `align.speech_seconds`, never the file length. Research: `docs/RESEARCH.md` "Dub timing".
- **"No audio was received" (edge-tts `NoAudioReceived`)** → Edge answers no audio at random (~9% of requests,
  measured 2026-10-16) and always for text without letters ("…", "—", "♪"). `tts.py` skips unspeakable lines, retries
  5×, falls back to the natural-speed clip, leaves one line silent as a last resort, and only fails the job when >20%
  of lines get no audio (= real outage).
- **Line untranslated / wrong language / gibberish** → check `segments_src_v3.json` `lang` per line (Whisper `base`
  detection per speech region) and `segments_<lang>_v3.translator` (google / offline). QA: `tools/qa_languages.py OUT --targets <lang>` dubs
  multilingual test clips and reports untranslated lines, Whisper re-listen, timing and back-translations;
  `tools/stub_server.py` runs the website with a stand-in pipeline for UI work (see docs/STATUS.md "How to test").
- **Nothing heard** → `ffprobe` the track wav; check `clips/` sizes (0-byte = TTS failed).
- **Slow** → transcription dominates on CPU; try `DUBBER_WHISPER_MODEL=base`.

## Extending
- New dub language: add a row to `dubber/languages.py` (Edge voices from `edge_tts.list_voices()`, Google code from
  `deep_translator.constants`, ISO 639-2 tag) and update the language count in `tests/test_app.py`; the UI reads `/api/languages`.
- New UI text: add the key to both `ru` and `en` in `dubber/web/i18n.js`; never hard-code strings in `app.js`/`index.html`.
- New translator: implement `translate_texts(list[str]) -> list[str]` (same length!) + `name`, wire in `make_backend`.
- New TTS: an async `synth(text, voice, out_path, rate)` (`rate` like `"+35%"`); pass via `synth=` or make it the default in `tts.py`.
- Every stage must stay testable offline: add a stub in `tests/test_pipeline.py` style, never call the network in tests.
