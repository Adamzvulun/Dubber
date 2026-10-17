# Status — read this first

_Last updated: 2026-10-17 (end of session 1). Update this page at the end of every session._

## In one paragraph
Dubber is a local website (FastAPI + hand-built front-end) that turns a YouTube video in **any spoken language** (also
mixed, e.g. English + French) into a **dubbed MP4 in one of 12 languages** (Russian by default) with subtitles and
transcripts. Built for Adam's father, a Russian-speaking professional who learns from foreign videos. It is installed and
running on **Adam's Windows PC**; Adam says the dub timing "works great". Latest work (2026-10-17): every dub language
now translates reliably (line languages, Google retries, NLLB offline backup, quality gate) and was QA-tested on 24
real dubs. **Waiting for Adam** to re-dub his English+French video with that fix.

## Where things are
- **Branch:** `claude/inspiring-davinci-4qon8o` — Adam starts new sessions from it. The repo's default branch
  `claude/bold-davinci-qfv627` is **outdated** (stops before the timing, languages and translation work); there is no
  `main`. Adam installs by downloading this branch's ZIP and running `scripts\install_windows.bat`.
- **Code:** `dubber/` (pipeline + `app.py`), `dubber/web/` (site, `i18n.js` = all UI text RU/EN), `tests/` (64 tests,
  offline), `tools/` (stub server, 12-language QA), `scripts/` (installers/launchers). Conventions: `CLAUDE.md`.
- **Docs:** `PLAN.md` (roadmap), `PROGRESS.md` (history, newest first), `DECISIONS.md` (ADR-001…016), `DESIGN.md`
  (design system), `RESEARCH.md` (tools, timing research, 12-language QA results), `SKILLS.md`, `README.ru.md`
  (father's guide). Task cards: `kanban/` (open items: `kanban/next-steps.md`).
- **Data on a user's PC:** `work/<id>/` = cache per video (`source.mp4`, `info.json`, `segments_src_v3.json` = what was
  said with each line's language, `speech_info.json`, `segments_<lang>_v3.json` + `.translator`, `clips_<voice>/`,
  `dub_track_<voice>_<hash>.wav`, `timing_<voice>_<hash>.json`); `output/<id>/` = what the library shows (`dubbed.mp4`,
  `meta.json` with `target_lang`/`source_lang(s)`/`files`/`translator`, `thumbnail.jpg`, `segments.json`,
  `timing.json`, `subtitles_<lang>|src.srt/.vtt`, `transcript_<lang>.txt`, `transcript_src_<lang>.txt`). Git-ignored.
  One video = one library entry: dubbing the same video into another language replaces the previous dub.

## How it works (one line per stage — details in the `dubber-pipeline` skill)
1. Download (yt-dlp + deno) → 2. Transcribe: Whisper `base` detects the language of every speech region, Whisper
`small` transcribes each language run with word timings → sentence lines (`segments.split_into_units`) → 3. Translate
(`translate.Translator`): lines already in the dub language kept; one-language batches to Google (retries 2-4-8-16-30 s)
or Claude (opt-in key); NLLB-200 1.3B offline backup; quality gate → 4. TTS twice (measure, then planned Edge `rate`,
`timing.plan_rates`) → 5. Align (trim Edge silence, lines on the speaker's start times, ≤1.1× correction) → 6. Mux
(language tags) + subtitles + meta.

## What works (verified by running it)
- Website: RU/EN interface, dub-language select, male/female voice, background switch, live job card with 6 steps,
  cancel (resume later), error cards with Russian/English messages, library, watch page with synced bilingual
  transcript (RTL for Hebrew/Arabic, keyboard-accessible), downloads, delete, dark mode, 360 px phones. Two QA agents
  reviewed it (2026-10-16); fixes re-verified in Chromium.
- Timing (ADR-013): all lines start on the speaker's timing, steady pace, no time-stretching (synthetic talk).
- **All 12 dub languages** (ADR-014/016): 24 real dubs (2 multilingual clips × 12): 0 untranslated lines, 0 late lines,
  Whisper re-hears 93–100 % of each dub, pace 0.90–1.60×; meaning read line by line (RESEARCH "Every dub language").
- Real YouTube runs (session 1b/1c): two TED-Ed videos, CLI and website.

## Not verified yet
1. **Google translation path end-to-end** — Google answers this cloud sandbox with HTTP 429, so the QA ran on the NLLB
   backup. Client logic is unit-tested; Adam's PC (home IP) normally gets Google.
2. **Adam's re-dub of his English+French video** with the 2026-10-17 fix (the new cache version re-transcribes it).
3. Fixed Windows desktop shortcut (Cyrillic name) — not re-reported by Adam.
4. H.264 playback in a real Chrome/Edge (test Chromium lacks H.264; logic verified with a VP9 copy).

## Next steps
1. Ask Adam how the re-dub of the EN+FR video sounds (and the other languages he tries); fix what he reports.
2. Known offline-backup slips to watch: Hebrew "flour" → "acid/vinegar"; speaker gender unknown to the translator;
   Whisper occasionally merges two sentences. A Claude key (`ANTHROPIC_API_KEY`, opt-in, paid) is the quality option.
3. Product gaps worth offering: several dub languages of the same video in the library (today one replaces the
   other); upload a local video file from the website (today: CLI only); glossary for the father's field.
4. Roadmap items in `PLAN.md` (M3/M4): voice speed control, Demucs (keep music without the original voice), queue.

## Gotchas for Claude in the cloud sandbox
- **Network:** the environment needs these hosts allowed (or "Full" access): `youtube.com`, `*.youtube.com`,
  `*.googlevideo.com`, `*.ytimg.com`, `youtubei.googleapis.com`, `huggingface.co`, `*.huggingface.co`, `*.hf.co`,
  `translate.googleapis.com`, `speech.platform.bing.com`. Fonts load from Google Fonts (optional).
- **YouTube blocks datacenter IPs** ("Sign in to confirm you're not a bot", then 403). For a real YouTube test, Adam
  must provide a fresh `cookies.txt`, stored **outside the repo** and passed via `DUBBER_COOKIES`. Never commit cookies.
  Without it, test with local files (`tools/qa_languages.py` makes multilingual clips with Edge voices).
- **Google Translate answers HTTP 429** from here → the `Translator` waits ~1 min, then uses the NLLB backup (the
  log says "unavailable … using the offline translator"). For quick runs pass `translator="offline"`.
- **Models downloaded on first use** (Hugging Face, cached in `~/.cache/huggingface`): Whisper `small` (~480 MB) and
  `base` (~140 MB); NLLB-200 1.3B int8 (~1.4 GB) only when the offline backup is needed.
- **Headless Chromium has no H.264.** For real playback make a VP9 copy:
  `ffmpeg -t 70 -i dubbed.mp4 -map 0:v:0 -map 0:a:0 -c:v libvpx-vp9 -b:v 300k -deadline realtime -cpu-used 8 -c:a libopus out.mp4`.
- **Playwright:** the venv has no playwright; use a separate venv (`python3 -m venv /tmp/pw && /tmp/pw/bin/pip install
  playwright`) and launch with `executable_path="/opt/pw-browsers/chromium"`; never run `playwright install`.
- **Killing a server:** `pkill -f dubber.app` also kills your own shell (exit 144). Kill by PID
  (`... & echo $! > pid` when starting, then `kill $(cat pid)`).
- **Copyright:** test dubs of third-party videos are for Adam's personal review only — don't commit or publish them or
  put their frames in `docs/images/` (current screenshots show only synthetic test clips).

## How to test
```bash
.venv/bin/ruff check . && .venv/bin/pytest                    # offline checks (must pass before every commit)
DUBBER_NETWORK_TESTS=1 .venv/bin/pytest -m network            # real NLLB model (downloads 1.4 GB once)

# UI work without network: the real website + a stand-in pipeline (6 stages ~30 s; URL with "fail" → error card)
.venv/bin/python tools/stub_server.py /tmp/stub 7871 & echo $! > /tmp/stub.pid
#   copy finished videos into /tmp/stub/out/<id>/ to test library/watch pages; drive with Playwright; kill by PID

# Translation + timing QA on real dubs (Edge voices, Whisper, NLLB): results.json + table.md
.venv/bin/python tools/qa_languages.py /tmp/qa --clips mixed,trio --targets ru,he   # all 12 if --targets omitted

# full pipeline: local file or YouTube URL (needs cookies in the cloud)
.venv/bin/python -m dubber.cli --lang he --voice female /path/to/video.mp4

# the real website on a separate data folder, without opening a browser
DUBBER_WORK_DIR=/tmp/x/work DUBBER_OUTPUT_DIR=/tmp/x/output DUBBER_PORT=7870 DUBBER_NO_BROWSER=1 \
  .venv/bin/python -m dubber.app
```
Check results with `ffprobe` (expect h264 + aac in the dub language + the original audio + mov_text in the dub
language; `mul` for a mixed-language original) and `output/<id>/timing.json` (late_lines, rates).
