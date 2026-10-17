# Status — read this first

_Last updated: 2026-10-18 (end of session 2). Update this page at the end of every session._

## In one paragraph
Dubber is a local website (FastAPI + hand-built front-end) that turns a YouTube video in **any spoken language** (also
mixed, e.g. English + French) into a **dubbed MP4 in one of 12 languages** (Russian by default) with subtitles and
transcripts. Built for Adam's father, a Russian-speaking professional (Windows PC, watches videos on every topic).
It runs on **Adam's Windows PC**. Current version **0.3.1** (shown in the page footer). Session 2 added: the `main`
branch + PR workflow + CI, the Claude translation option (Settings page: key, model, glossary), a time-left estimate,
and fixes so updates are always visible. **Open:** Adam's report that translation/timing got worse after the
language work (waiting for his files), the installer seeming stuck after "Obtaining file:///…" (changed in 0.3.1,
waiting for his re-run), and a first real dub with a Claude key.

## Where things are
- **Git:** `main` = stable; Adam installs from its ZIP. Work happens on a branch + PR into `main`; CI (lint + tests)
  must be green; **Adam reviews and merges**. **Branch rule (Adam, 2026-10-18): a new branch only for a new feature;
  fixes and follow-ups to the current work go on the same branch** (this session: `claude/inspiring-davinci-4qon8o`).
  Details: `CONTRIBUTING.md`. Files Adam shares arrive on `uploads/…` branches in `dev-uploads/`.
- **Code:** `dubber/` (pipeline stages, `app.py` = server/API/jobs/settings, `eta.py` = time left, `config.py` =
  settings + `save_env`), `dubber/web/` (site; `i18n.js` = all UI text RU/EN), `tests/` (90 tests, offline),
  `tools/` (stub server, 12-language QA), `scripts/` (installers/launchers). Conventions: `CLAUDE.md`.
- **Docs:** `PLAN.md` (roadmap), `PROGRESS.md` (history, newest first), `DECISIONS.md` (ADR-001…018), `DESIGN.md`
  (design system), `RESEARCH.md` (tools, timing research, 12-language QA), `SKILLS.md`, `README.ru.md` (father's
  guide: install, update, Claude key, troubleshooting). Task cards: `kanban/` (hand-off list: `kanban/next-steps.md`).
- **Data on a user's PC (git-ignored):** `.env` (settings saved by the website, incl. the Claude key),
  `glossary.txt`, `install.log` (last installer run), `work/<id>/` = cache per video (`source.mp4`, `info.json`,
  `segments_src_v3.json` = what was said with each line's language, `speech_info.json`, `segments_<lang>_v3.json` (free
  engines) / `segments_<lang>_v3_claude_<hash>.json` + `.info.json` (engine, cost, notes), `clips_<voice>/`,
  `dub_track_<voice>_<hash>.wav`, `timing_<voice>_<hash>.json`), `work/stage_times.json` (stage timings of the last
  10 dubs, for the time-left estimate); `output/<id>/` = what the library shows (`dubbed.mp4`, `meta.json` with
  languages/files/translator/cost, `thumbnail.jpg`, `segments.json`, `timing.json`, subtitles, transcripts).
  One video = one library entry: dubbing it into another language replaces the previous dub.

## How it works (one line per stage — details in the `dubber-pipeline` skill)
1. Download (yt-dlp + deno) → 2. Transcribe: Whisper `base` detects the language of every speech region, Whisper
`small` transcribes each language run with word timings → sentence lines (`segments.split_into_units`) → 3. Translate
(`translate.Translator`): lines already in the dub language kept; Claude (opt-in key) gets the whole video with time
slots, else one-language batches to Google (retries 2-4-8-16-30 s); fallback chain Claude → Google → NLLB-200 1.3B
offline; quality gate → 4. TTS twice (measure, then planned Edge `rate`,
`timing.plan_rates`) → 5. Align (trim Edge silence, lines on the speaker's start times, ≤1.1× correction) → 6. Mux
(language tags) + subtitles + meta.

## What works (verified by running it)
- **0.3.1 — updates always visible (ADR-018):** the app serves `index.html` with versioned file addresses
  (`?v=<version>.<newest file time>`) + `no-cache`; reproduced Adam's "new page, old styles" and verified fixed; a
  simulated next release shows on the first open. A second start says "already running (version …)" instead of
  showing the old page. Version in footer, `/api/version`, start message.
- **Time left on the job card (`eta.py`, ADR-018):** stage shares learned from this PC's past dubs; within ~1–3 s of the
  truth on a stub job. Not yet seen on a real long dub.
- **Claude translation (ADR-017):** Settings page (key check + save + mask + remove, model, on/off, glossary), Origin
  check on state-changing API calls, whole-video requests with time slots and character budgets, fallback chain
  Claude → Google → offline with reasons, cost on the watch page. Real SDK verified only with a dummy key.
- Website: RU/EN interface, dub-language select, voices, background switch, job card (6 steps, elapsed + time left,
  cancel), error cards, library, watch page with synced bilingual transcript (RTL), downloads, delete, dark mode,
  360 px phones.
- Timing (ADR-013), all 12 dub languages (ADR-014/016: 24 real QA dubs), real YouTube runs (session 1).

## Not verified yet
1. **A real Claude translation** (needs Adam's key): quality, cost, and whether timing beats the free path.
2. **Installer change in 0.3.1** (no pip build isolation + `install.log`): verified in a fresh Linux venv only; Adam's
   Windows run pending.
3. **Google translation end-to-end** (Google answers this sandbox with HTTP 429; Adam's PC normally gets Google).
4. H.264 playback in a real Chrome/Edge; the fixed desktop shortcut (Cyrillic name) — not re-reported by Adam.

## Next steps (in order)
1. **Adam updates to 0.3.1** (close windows → extract over the old folder → `install_windows.bat`; clear cached files
   once if the page looks broken). Confirm: footer 0.3.1, Settings page looks right. If the installer stalls again:
   ask for `install.log` (in the program folder) on an `uploads/…` branch.
2. **Translation/timing regression** (`kanban/translation-timing-regression.md`): read his files from `dev-uploads/`
   (on an `uploads/…` branch), compare old (`*_v2`) and new (`*_v3`) caches, find the cause, fix.
3. **First dub with a Claude key**: check `meta.json` (translator, cost) and `timing.json` against a free dub;
   calibrate `languages.chars_per_second` if lines run long.
4. Product ideas to offer: several dub languages of one video in the library; upload a local file from the website;
   voice speed control; Demucs (keep music without the original voice); queue (PLAN M3/M4).
5. Known offline-backup slips: Hebrew "flour" → "acid/vinegar"; speaker gender unknown to the translator.

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
Every release: bump `__version__` in `dubber/__init__.py` and `pyproject.toml` (shown in the footer).

```bash
.venv/bin/ruff check . && .venv/bin/pytest                    # offline checks (must pass before every commit)
DUBBER_NETWORK_TESTS=1 .venv/bin/pytest -m network            # real NLLB model (downloads 1.4 GB once)

# UI work without network: the real website + a stand-in pipeline (6 uneven stages ~31 s; URL with "fail" → error
# card; settings kept in the data folder; a Claude key ending in "bad" is refused)
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
