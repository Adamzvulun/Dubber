---
name: dubber-pipeline
description: How the Dubber YouTube→Russian dubbing pipeline works and how to run, debug or extend a stage (download, transcribe, translate, tts, align, mux). Use whenever touching code in dubber/ or investigating a bad dub (wrong timing, missing audio, translation problems, download failures).
---

# Dubber pipeline

`dubber/pipeline.py::run(source, settings, progress, translator=, synth=, transcriber=)` runs:

| # | Stage | Module | Cache file in `work/<video-id>/` |
|---|---|---|---|
| 1 | Download (yt-dlp or local copy) | `download.py` | `source.mp4` |
| 2 | Transcribe EN (faster-whisper) + merge into sentences | `transcribe.py`, `segments.py` | `audio_16k.wav`, `segments_en.json` |
| 3 | Translate EN→RU (Google free / Claude) | `translate.py` | `segments_ru.json` |
| 4 | TTS per segment (edge-tts) | `tts.py` | `clips/00000.mp3 …` |
| 5 | Fit clips to timing, build track | `align.py` | `russian_track_<voice>.wav` |
| 6 | Subtitles + final MP4 | `subtitles.py`, `mux.py` | `output/<title>/` |

**Resume/cache rule:** a stage is skipped if its cache file exists. To redo a stage, delete its file
and everything after it (e.g. new translation → delete `segments_ru.json`, `clips/`, `russian_track_*.wav`).

## Running
```bash
.venv/bin/python -m dubber.cli "https://www.youtube.com/watch?v=..."   # or a local .mp4
.venv/bin/python -m dubber.app                                          # web UI
DUBBER_WHISPER_MODEL=tiny  DUBBER_TRANSLATOR=google  DUBBER_VOICE=ru-RU-SvetlanaNeural  # env knobs (see config.py)
```

## Debugging checklist
- **Download fails (403 / "confirm you're not a bot")** → `pip install -U yt-dlp` first; then see the
  `youtube-downloader` skill references (cookies, PO tokens). Cloud/datacenter IPs are often blocked.
- **Russian voice too fast / overlapping** → inspect `segments_ru.json` durations; tune `DUBBER_MAX_SPEEDUP`;
  long Russian lines are best fixed at translation (Claude prompt asks for concise wording).
- **Nothing heard** → `ffprobe` the track wav; check `clips/` sizes (0-byte = TTS failed).
- **Slow** → transcription dominates on CPU; try `DUBBER_WHISPER_MODEL=base`.

## Extending
- New translator: implement `translate_texts(list[str]) -> list[str]` (same length!) + `name`, wire in `make_backend`.
- New TTS: an async `synth(text, voice, out_path)`; pass via `synth=` or make it the default in `tts.py`.
- Every stage must stay testable offline: add a stub in `tests/test_pipeline.py` style, never call the network in tests.
