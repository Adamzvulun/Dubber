# Status — read this first

_Last updated: 2026-10-16 (session 1i: languages, cancel, RU/EN UI, QA). Update this page at the end of every session._

## In one paragraph
Dubber is a local website (FastAPI + hand-built front-end) that turns a YouTube video in any spoken language (also
mixed, e.g. English + French) into a dubbed MP4 in one of 12 languages (Russian by default) with subtitles and
transcripts (every language QA-tested: translation, re-listen, timing — RESEARCH "Every dub language"). It is built for Adam's father, a Russian-speaking professional who learns from foreign videos. It runs on
Adam's Windows PC; Adam reports the dub timing "works great". The UI has a RU/EN switch and a cancel button.

## Where things are
- **Branch:** current work is on `claude/inspiring-davinci-4qon8o` (pushed; builds on `claude/bold-davinci-qfv627`).
  **Not merged to `main` yet** — Adam may want a PR so "Download ZIP" on the repo page just works.
- **Code:** `dubber/` (pipeline stages + `app.py` server), `dubber/web/` (site), `tests/` (64 tests, offline),
  `scripts/` (installers/launchers). Architecture and conventions: `CLAUDE.md`.
- **Docs:** `PLAN.md` (roadmap), `PROGRESS.md` (history), `DECISIONS.md` (ADRs 001–016), `DESIGN.md` (site design system),
  `RESEARCH.md` (tools + real-world findings), `SKILLS.md` (installed Claude skills), `README.ru.md` (father's guide).
- **Data on a user's PC:** `work/<id>/` = cache per video (`source.mp4`, `info.json`, `segments_src_v3.json` (original, any
  language, with line languages), `speech_info.json`, `segments_<lang>_v3.json` (+ `.translator`), `clips_<voice>/`,
  `dub_track_<voice>_<hash>.wav`, `timing_<voice>_<hash>.json`); `output/<id>/` = what the library shows (`dubbed.mp4`, `meta.json`,
  `thumbnail.jpg`, `segments.json`, `timing.json`, `subtitles_*.srt/.vtt`, `transcript_*.txt`). Both are git-ignored.

## What works (verified by running it)
- Download (yt-dlp + deno), transcription (faster-whisper `small`, CPU), translation (Google → automatic offline
  fallback; Claude optional), Russian voice (edge-tts Dmitry/Svetlana), timing fit, final MP4 with RU audio (default),
  EN original as track 2, soft RU subtitles.
- Website: new-video page with live 6-step job card, library, watch page with synced bilingual transcript
  (click a line to seek), downloads, delete, dark mode, phone layout, option "without original sound".
- Real runs: "The science of spiciness" (3:55, ~3.8 min CPU) and "What is imposter syndrome" (4:19, 250 s) —
  streams/durations checked with ffprobe; Whisper listening to the dub detects Russian (p=1.00, 91 % words match).

## Not verified yet
1. Windows installer: works on Adam's PC (shortcut + model-download fixes since); re-test the fixed shortcut.
4. New dub timing (ADR-013) on a real YouTube video, by ear — verified only on a synthetic talk here.
2. H.264 playback inside a real Chrome/Edge (test Chromium lacks H.264; playback logic verified with a VP9 copy).
3. Google translation quality from a home connection (Google blocks the cloud test server, so only the offline
   translator was exercised — its Russian is understandable but literal).

## Next steps
1. Adam re-dubs a video with the new timing and listens; check `output/<id>/timing.json` (`kanban/dub-timing.md`).
2. Optional: PR `claude/bold-davinci-qfv627` → `main`.
3. Translation quality: decide on a Claude API key (opt-in, ~$0.05–0.20 per 10-min video) and/or a glossary for the
   father's field.
4. M3 items in `PLAN.md`: voice speed control, Demucs (keep music without English voice).
5. Open questions for Adam: father's work field; his OS (Windows assumed).

## Gotchas for Claude in the cloud sandbox
- **Network:** the environment needs these hosts allowed (or "Full" access): `youtube.com`, `*.youtube.com`,
  `*.googlevideo.com`, `*.ytimg.com`, `youtubei.googleapis.com`, `huggingface.co`, `*.huggingface.co`, `*.hf.co`,
  `translate.google.com`, `translate.googleapis.com`, `speech.platform.bing.com`. Fonts load from Google Fonts (optional).
- **YouTube blocks datacenter IPs** ("Sign in to confirm you're not a bot", then 403). Fix for tests: a fresh
  `cookies.txt` from Adam (exported with "Get cookies.txt LOCALLY"), stored **outside the repo** (scratchpad) and
  passed via `DUBBER_COOKIES`. The cookies from session 1 are no longer accepted. Never commit cookies.
- **Google Translate blocks datacenter IPs** → the run silently uses the offline translator (see the log line
  "switching to the offline translator").
- **Headless Chromium has no H.264.** To test real playback, make a VP9 copy:
  `ffmpeg -t 70 -i dubbed.mp4 -map 0:v:0 -map 0:a:0 -c:v libvpx-vp9 -b:v 300k -deadline realtime -cpu-used 8 -c:a libopus out.mp4`.
- **Playwright:** launch with `executable_path="/opt/pw-browsers/chromium"`; never run `playwright install`.
- **Killing the server:** `pkill -f dubber.app` also kills your own shell (exit 144). Use
  `for p in $(ps -eo pid,args | awk '/python -m dubber.app/ && !/awk/ {print $1}'); do kill $p; done`.
- **First run downloads models:** Whisper `small` (~460 MB) and the offline translator (~110 MB) from Hugging Face.
- **Copyright:** test dubs of third-party videos are for Adam's personal review only — don't commit them, publish
  them, or put their frames in `docs/images/`.

## How to test for real (cloud)
```bash
# offline checks
.venv/bin/ruff check . && .venv/bin/pytest
DUBBER_NETWORK_TESTS=1 .venv/bin/pytest -m network        # real offline-translator model

# full pipeline from the command line
DUBBER_COOKIES=/path/outside/repo/cookies.txt .venv/bin/python -m dubber.cli "https://youtu.be/qD0_yWgifDM"

# the website on a separate data folder, without opening a browser
DUBBER_WORK_DIR=/tmp/x/work DUBBER_OUTPUT_DIR=/tmp/x/output DUBBER_PORT=7870 DUBBER_NO_BROWSER=1 \
  .venv/bin/python -m dubber.app
```
Then drive it with Playwright (fill «Ссылка на видео», click «Озвучить», wait for `.job--done`) and check the
result with `ffprobe` (expect h264 + aac rus + aac eng + mov_text rus; same duration as the source).
