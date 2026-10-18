# Status — read this first

_Last updated: 2026-10-18 (session 5). Update this page at the end of every session._

## In one paragraph
Dubber is a local website (FastAPI + hand-built front-end) that turns a YouTube video **or a video file** in **any
spoken language** (also mixed, e.g. English + French) into a **dubbed MP4 in one of 12 languages** (Russian by
default) with subtitles and transcripts. For a Russian speaker on a Windows PC who learns from videos on every topic.
Current version **0.6.1** (page footer). The PCs **update themselves from `main`** (ADR-024): merging is shipping.
Session 5: one-click Windows start (`Start Dubber.cmd` → install + desktop shortcut with its own icon + start; the
old `?` / missing-shortcut bug reproduced and fixed on real Windows in CI, ADR-025), file upload, several links and
playlists (ADR-026), grouped library with search, disk space page, "What's new" after updates (ADR-027).
Earlier: per-dub library entries + self-update (session 4), voice removal and transcription fixes (session 3).

## Where things are
- **Git:** `main` = stable and **shipped**: from 0.5.0 the PCs update themselves from `main` (needs the repo
  public; one last manual ZIP update to reach 0.5.0). Every release must bump the version. Work happens on a branch + PR into `main`; CI (lint + tests)
  must be green; **Adam reviews and merges**. **Branch rule (Adam, 2026-10-18): a new branch only for a new feature;
  fixes and follow-ups to the current work go on the same branch** (this session: `claude/inspiring-davinci-4qon8o`).
  Details: `CONTRIBUTING.md`. Files Adam shares arrive on `uploads/…` branches in `dev-uploads/`.
- **Code:** `dubber/` (pipeline stages, `app.py` = server/API/jobs/settings, `eta.py` = time left, `config.py` =
  settings + `save_env`, `separate.py` = voice removal), `dubber/web/` (site; `i18n.js` = all UI text RU/EN),
  `update.py` = self-update, `changelog.json` = "What's new", `assets/` = logo + Windows icon), `tests/` (127 tests,
  offline), `tools/` (stub server, 12-language QA, Hebrew voice QA, `make_icon.py`), `Start Dubber.cmd` +
  `scripts/windows/dubber.ps1` (Windows start, ADR-025), `scripts/` (old launchers, macOS/Linux). Conventions:
  `CLAUDE.md`.
- **Docs:** `PLAN.md` (roadmap), `PROGRESS.md` (history, newest first), `DECISIONS.md` (ADR-001…027), `DESIGN.md`
  (design system), `RESEARCH.md` (tools, timing research, 12-language QA), `SKILLS.md`, `README.ru.md` (user's
  guide: install, update, Claude key, troubleshooting). Task cards: `kanban/` (hand-off list: `kanban/next-steps.md`).
- **Data on a user's PC (git-ignored):** `.env` (settings saved by the website, incl. the Claude key),
  `glossary.txt`, `install.log` (last installer run), `.venv/dubber-installed` (components installed),
  `work/uploads/<sha>/<name>` = uploaded videos until dubbed, `work/<id>/` = cache per video (`source.mp4`, `info.json`,
  `segments_src_v3.json` = what was said with each line's language, `speech_info.json`, `segments_<lang>_v3.json` (free
  engines) / `segments_<lang>_v3_claude_<hash>.json` + `.info.json` (engine, cost, notes), `clips_<voice>/`,
  `dub_track_<voice>_<hash>.wav`, `timing_<voice>_<hash>.json`, `background_htdemucs.wav` = original without the
  voice, only when that switch was on), `work/stage_times.json` (stage timings of the last
  10 dubs, for the time-left estimate); `output/<id>/` = what the library shows (`dubbed.mp4`, `meta.json` with
  languages/files/translator/cost, `thumbnail.jpg`, `segments.json`, `timing.json`, subtitles, transcripts).
  One **dub** = one library entry: `output/<video-id>--<lang>-<hash>/` (hash of language, voice, background,
  voice removal; `pipeline.dub_id`); redoing the same choices replaces it. Folders from before 0.4.1 are named
  `output/<video-id>/` and still work.

## How it works (one line per stage — details in the `dubber-pipeline` skill)
1. Download (yt-dlp + deno) → 2. Transcribe: Whisper `base` detects the language of every speech region, Whisper
`small` transcribes each language run with word timings (each region gets one of the video's languages,
`transcribe.video_languages`; runs keep up to 1 s around them) → sentence lines (`segments.split_into_units`) → 3. Translate
(`translate.Translator`): lines already in the dub language kept; Claude (opt-in key) gets the whole video with time
slots, else one-language batches to Google (retries 2-4-8-16-30 s); fallback chain Claude → Google → NLLB-200 1.3B
offline; quality gate → 4. TTS twice (measure, then planned Edge `rate`,
`timing.plan_rates`) → 5. Align (trim Edge silence, lines on the speaker's start times, ≤1.1× correction) → 6. Mux
(language tags) + subtitles + meta. Optional before 6: `separate.py` (Demucs ONNX) removes the
original voice; the voice-free background goes under the dub, ducked while it speaks.

## What works (verified by running it)
- **0.6.0 — one-click Windows start (ADR-025):** CI on `windows-latest` (Windows PowerShell 5.1): fresh install,
  existing install recognised without reinstalling, desktop + Start menu «Дубляж видео» shortcuts with the icon
  read back, `Start Dubber.cmd` starts the program and it answers. Russian text shows correctly in the window.
- **0.6.0 — upload, several links, playlists, grouped library + search, disk space, "What's new"**: tested in
  Chromium on the stub server (RU/EN, 360/1280 px; playlists faked — YouTube is blocked here) + unit tests.
- **0.5.0 — self-update (ADR-024):** rehearsed with a fake GitHub on localhost: update at start (data kept, new
  version started) and with the button in Chromium (page reloads on the new version). Not yet seen against the
  real GitHub (repo still private when built) or on Windows.
- **0.4.1 — one library entry per dub (ADR-022):** two pipeline runs of one clip (ru, en) give two folders with
  the right audio each; in Chromium each card plays its own dub and «Другие озвучки этого видео» switches between
  them (RU desktop, EN 360 px dark).
- **0.4.0 — voice removal (ADR-020):** switch «Убрать голос диктора» (off by default), CLI `--remove-voice`; on a
  test mix no words remain in the background and the music level is unchanged; end-to-end dub verified (Russian
  voice + music, original track intact); ≈ +5 min per 10-min video on 4 cores. UI checked RU/EN, 360 px, dark.
- **Transcription fixes (ADR-021):** on real FLEURS speech, mixed EN+FR errors 0.199 → 0.153; Hebrew regions no
  longer transcribed as Italian/French.
- **Hebrew voice measured (ADR-019):** `tools/qa_hebrew_voice.py`; plain Edge kept.
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
1. **Claude request v2** (ADR-021, spelling notes ADR-019): unit-tested only (no key here). Adam's first dub on 0.4.0
   with Claude re-translates once (new prompt version) — check quality and `meta.json` cost.
2. Voice removal speed and quality on Adam's PC and on real videos (music, noise, several speakers).
3. **Google translation end-to-end** (Google answers this sandbox with HTTP 429; Adam's PC normally gets Google).
4. H.264 playback in a real Chrome/Edge.
5. **First run on a clean PC** (winget installing Python + ffmpeg): CI had both preinstalled. Real YouTube playlists
   (flat extraction) — only mocked here. A large upload (GBs) — only small files tested.

## Next steps (in order)
1. **Adam merges PR #9** → both PCs update to 0.6.0 by themselves; the old shortcut (→ `start_windows.bat`) now runs
   the new script once, which replaces it with the «Дубляж видео» shortcut with the icon. Check: icon on the desktop,
   "What's new" card, upload a file, a playlist link.
2. Is the repo public? Self-update needs it (ADR-024).
3. Still open from session 3: listen to a Hebrew dub and an English Claude dub; voice removal on real videos.
4. Ideas not yet chosen: voice speed control; Hebrew spelling fix on the free path; offline TTS fallback (Silero).
5. Known limits: Hebrew homographs and grammatical gender (לך) can't be read right from plain text by any voice;
   speaker gender unknown to the translator; offline-backup slips (Hebrew "flour" → "acid/vinegar").

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
- **Killing:** `pkill -f X` / `pgrep -f X` also match your own shell command (exit 144) — even inside a wait loop.
  Use the PID (`$!`) or `pgrep -f "python -I .*script"`.
- **Killing a server:** `pkill -f dubber.app` also kills your own shell (exit 144). Kill by PID
  (`... & echo $! > pid` when starting, then `kill $(cat pid)`).
- **Copyright:** test dubs of third-party videos are for Adam's personal review only — don't commit or publish them or
  put their frames in `docs/images/` (current screenshots show only synthetic test clips).

## How to test
Every release: bump `__version__` in `dubber/__init__.py` and `pyproject.toml` (shown in the footer) and add its
changes to `dubber/changelog.json`.

Windows start (`scripts/windows/dubber.ps1`): no Windows here — parse-check with PowerShell 7 for Linux (download the
`powershell-7.x-linux-x64.tar.gz` release into the scratchpad, then
`pwsh -c '[System.Management.Automation.Language.Parser]::ParseFile(...)'`); the real test is the `Windows install`
CI job on the PR (read its log with the GitHub tools). Keep the `.ps1` UTF-8 with BOM. Icon: render
`dubber/assets/logo.svg` to PNGs (Chromium) and pack with `tools/make_icon.py`.

```bash
.venv/bin/ruff check . && .venv/bin/pytest                    # offline checks (must pass before every commit)
DUBBER_NETWORK_TESTS=1 .venv/bin/pytest -m network            # real NLLB model (downloads 1.4 GB once)

# UI work without network: the real website + a stand-in pipeline (6 uneven stages ~31 s; URL with "fail" → error
# card; settings kept in the data folder; a Claude key ending in "bad" is refused)
.venv/bin/python tools/stub_server.py /tmp/stub 7871 & echo $! > /tmp/stub.pid
#   copy finished videos into /tmp/stub/out/<id>/ to test library/watch pages; drive with Playwright; kill by PID

# Translation + timing QA on real dubs (Edge voices, Whisper, NLLB): results.json + table.md
.venv/bin/python tools/qa_languages.py /tmp/qa --clips mixed,trio --targets ru,he   # all 12 if --targets omitted

# self-update rehearsal without GitHub: serve DIR/main/dubber/__init__.py + DIR/main.zip (GitHub-style ZIP with one
# top folder) over http, then start an install folder (not a git checkout) with DUBBER_UPDATE_SOURCE=http://… set
# (the stub server shows the banner with STUB_UPDATE=9.9.9)

# full pipeline: local file or YouTube URL (needs cookies in the cloud)
.venv/bin/python -m dubber.cli --lang he --voice female /path/to/video.mp4

# the real website on a separate data folder, without opening a browser
DUBBER_WORK_DIR=/tmp/x/work DUBBER_OUTPUT_DIR=/tmp/x/output DUBBER_PORT=7870 DUBBER_NO_BROWSER=1 \
  .venv/bin/python -m dubber.app
```
Check results with `ffprobe` (expect h264 + aac in the dub language + the original audio + mov_text in the dub
language; `mul` for a mixed-language original) and `output/<id>/timing.json` (late_lines, rates).
