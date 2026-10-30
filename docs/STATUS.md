# Status — read this first

_Last updated: 2026-10-30 (end of session 9). Update this page at the end of every session._

## In one paragraph
Dubber is a local website (FastAPI + hand-built front-end) that turns a **YouTube, TikTok, Instagram or Facebook**
video **or a video file** in **any spoken language** (also mixed, e.g. English + French) into a **dubbed MP4 in one of 12 languages** (Russian by
default) with subtitles and transcripts. For a Russian speaker on a Windows PC who learns from videos on every topic.
Current version: **0.11.0** on `main` (PR #20, merged 2026-10-30) — nothing open; the session branch
`claude/modest-thompson-pp54kx` equals `main`. The repo is **public** and the PCs **update themselves from `main`** at start (ADR-024) — merging is
shipping. The phone version (0.10.0) is merged but **switched off** until Adam's Cloudflare mailbox address is put in
`phone.MAILBOX_URL` (see Next steps 1).
Session 7 (2026-10-28): **0.8.0 (merged, PR #13)** — the Windows install broke for anyone with Python 3.15 (released
Oct 2026; no onnxruntime build) → launchers use only Python 3.10–3.14, Microsoft C++ runtime installed, no-winget
fallback, component self-check `dubber/deps.py` at every start (ADR-029); on-screen subtitles: two switches under the
player (ADR-030). **0.9.0 (PR #14)** — TikTok/Instagram/Facebook links (ADR-031); public videos need **no login**
thanks to yt-dlp's `curl-cffi` extra (browser impersonation, ADR-032; research in `docs/RESEARCH.md`); a login file
(«Вход на сайты») only for private posts.
Session 5 (2026-10-18): one-click Windows start `Start Dubber.cmd` with a desktop shortcut and its own icon (the old
`?`/no-shortcut bug reproduced and fixed on real Windows in CI, ADR-025); upload a file, several links, playlists
(ADR-026); grouped library + search, disk space page, "What's new" after updates (ADR-027); 0.6.1: console font
switched to Consolas (Russian showed as `?` in the window) and the shortcut appears by itself after a self-update;
**README.md now opens with full user guides in Russian and Hebrew** (every function, Claude step by step).
Earlier: per-dub library entries + self-update (session 4), voice removal and transcription fixes (session 3).

Session 8 (2026-10-28/29), PRs #15–#17:
- Settings stays one 760 px column (Adam turned down two columns).
- **0.10.0 — phone version (ADR-033):** the same website as a home-screen app on Samsung/iPhone. The PC is reached
  through a free Cloudflare quick tunnel (`dubber/phone.py`, cloudflared downloaded by the program, no account); a
  mailbox Worker on Adam's Cloudflare account (`cloud/worker/`) serves the phone app and keeps links while the PC is
  off; pairing by QR code in Settings → «Телефон».
- **0.10.1 — NVIDIA PCs (ADR-034):** every dub failed on a PC with an NVIDIA card ("cublas64_12.dll is not found"):
  Whisper now falls back to the processor, and `dubber/gpu.py` installs NVIDIA's cuBLAS/cuDNN in the background so
  Whisper runs on the card.
- **0.10.2 — «Оригинал» (ADR-035, PR #17):** a real card check (Settings line; no hours-long CPU dubs: `clone:no_gpu`
  → Edge voice), device/timing lines in the program window, the install progress bar, voice-free background always
  with «Оригинал»; a QA pass by two agents (desktop + phone) and its fixes.

Session 9 (2026-10-29/30), PRs #18–#20, all merged: Adam's first «Оригинал» dub on the RTX 5060 Ti — voice copy good, card ~50% busy, words
"swallowed or warped" (lines told to last 0.14–0.26 s, crowded stretches 1.6×). **0.10.3 (ADR-036):** each line asks
for at least `clone.min_seconds` (≤ 7 syllables/s); 12/8/4 lines per call by card memory, longest first, a failing
group halved. His "no background" was a job with the background switch off (`meta.json`). **0.10.4 (ADR-037):**
"still cut off; words left in English" → measured OmniVoice (slips are random and word-dependent), so the copied voice
is hurried ≤ 1.25× and Whisper listens to every clip (garbled → up to 3 tries, `check.json`); Claude prompt v3 writes
names in the dub language's letters. **0.11.0:** `speakers.py` (voice prints of the lines, sherpa-onnx CAM++,
ADR-038) → one sample per speaker + different speakers may overlap; soft fades at line edges (ADR-040); every dub its
own library entry with date + time (ADR-039, replaces ADR-022's "same choices replace").

## Where things are
- **Git:** `main` = stable and **shipped** (PCs self-update from it; every release bumps the version and adds a
  `dubber/changelog.json` entry). Code changes: a branch + PR into `main`; CI (`CI` lint + tests, and `Windows install`
  when scripts/assets/app change) must be green; **Adam reviews and merges**. Use the branch your session's system
  prompt names (or `feat/…`, CONTRIBUTING). **Doc-only edits went straight to `main` when Adam asked** (README guides,
  this hand-off, 2026-10-18/19) — only do that when he says so. Old remote branches (`claude/bold-davinci-qfv627`,
  merged `fix/…`, `feat/…`, `chore/…`, earlier `claude/…`) are history; ignore them. Files Adam shares arrive on
  `uploads/…` branches in `dev-uploads/`.
- **Code:** `dubber/` (pipeline stages, `app.py` = server/API/jobs/settings, `eta.py` = time left, `config.py` =
  settings + `save_env` + local ffmpeg on PATH, `separate.py` = voice removal, `sites.py` = TikTok/Instagram/Facebook +
  login file, `deps.py` = component self-check run by the launcher, `clone.py` = «Оригинал» voice + its installer +
  card check + listen-back check + per-speaker references, `speakers.py` = who says each line (voice prints,
  sherpa-onnx), `phone.py` = the phone: cloudflared tunnel + mailbox, `gpu.py` = NVIDIA libraries for Whisper),
  `dubber/web/` (site; `i18n.js` = all UI text RU/EN; also the phone app: `manifest.webmanifest`, `sw.js`, `icons/`,
  phone mode in `app.js` under `/p/<token>/` — keep file addresses relative), `cloud/` (mailbox Worker
  `cloud/worker/` + its Node tests, `cloud/build.py` = phone app build), `update.py` = self-update, `changelog.json` =
  "What's new", `assets/` = logo + Windows icon), `tests/` (213 tests, offline), `tools/` (stub server,
  `phone_dev.mjs` = local Cloudflare stand-in, 12-language QA, Hebrew voice QA, `make_icon.py`,
  `make_phone_icons.js`), `Start Dubber.cmd` +
  `scripts/windows/dubber.ps1` (Windows start: install, shortcut, font, start; `-NoStart`, `-ShortcutOnly`; ADR-025),
  `scripts/` (old `.bat` launchers that now call `dubber.ps1`; macOS/Linux scripts), `.github/workflows/`
  (`ci.yml`; `windows-install.yml` = jobs `install` + `clean-pc` (no winget, Cyrillic folder, too-new venv rebuilt,
  repair, curl-cffi check, real cloudflared tunnel 401/200, NVIDIA wheels resolve); `original-voice-install.yml` (also
  runs pytest on Windows); `deploy-phone.yml` (mailbox Worker on merges to `main`; no-op without the Cloudflare
  secrets)). Conventions: `CLAUDE.md`.
- **Docs:** `PLAN.md` (roadmap), `PROGRESS.md` (history, newest first), `DECISIONS.md` (ADR-001…040), `DESIGN.md`
  (design system), `RESEARCH.md` (tools, timing research, 12-language QA, VoiceStudio/OmniVoice, TikTok/Instagram/Facebook without a
  login, OmniVoice speed limits, who speaks each line), `SKILLS.md`, `README.ru.md` (longer Russian
  reference). **User guides (RU + HE) are at the top of `README.md`** — they quote UI labels from `i18n.js`. Task cards: `kanban/` (hand-off list: `kanban/next-steps.md`).
- **Data on a user's PC (git-ignored):** `.env` (settings saved by the website, incl. the Claude key and
  `DUBBER_PHONE_TOKEN` = the household's phone secret), `cloudflared/` (the tunnel program, downloaded at the first
  start), `work/gpu-install.log` / `work/omnivoice-install.log` (NVIDIA libraries / «Оригинал» installs),
  `cookies.txt` (site logins from «Вход на сайты»: only YouTube/TikTok/Instagram/Facebook cookies), `ffmpeg/` (when
  winget was missing),
  `glossary.txt`, `install.log` (last installer run), `.venv/dubber-installed` (components installed),
  `work/uploads/<sha>/<name>` = uploaded videos until dubbed, `work/<id>/` = cache per video (`source.mp4`, `info.json`,
  `segments_src_v3.json` = what was said with each line's language, `speech_info.json`, `segments_<lang>_v3.json` (free
  engines) / `segments_<lang>_v3_claude_<hash>.json` + `.info.json` (engine, cost, notes), `clips_<voice>/`,
  `dub_track_<voice>_<hash>.wav`, `timing_<voice>_<hash>.json`, `background_htdemucs.wav` = original without the
  voice (voice removal or «Оригинал»), «Оригинал» only: `vocals_htdemucs.wav` + `vocals_24k.f32` = the voice alone,
  `speakers_<hash>.json` = speaker per line, `clips_original_<lang>/` + its `check.json` = what Whisper heard per
  line), `work/stage_times.json` (stage timings of the last
  10 dubs, for the time-left estimate); `output/<id>/` = what the library shows (`dubbed.mp4`, `meta.json` with
  languages/files/translator/cost, `thumbnail.jpg`, `segments.json`, `timing.json`, subtitles, transcripts).
  One **dub** = one library entry: `output/<video-id>--<lang>-<hash>-<YYYYMMDD-HHMMSS>/` (hash of language, voice,
  background, voice removal + the dub's time; `pipeline.dub_id`, ADR-039): every run is a new entry, even with the
  same choices. Older folders (`…--<lang>-<hash>/`, before 0.4.1 `output/<video-id>/`) still work. The library
  groups a video's dubs on one card (ADR-027) — Adam now wants one card per dub (Next steps 1).

## How it works (one line per stage — details in the `dubber-pipeline` skill)
1. Download (yt-dlp + deno + curl-cffi impersonation; YouTube/TikTok/Instagram/Facebook or a file; optional
`cookies.txt` login file; anything not H.264 re-encoded to H.264) → 2. Transcribe: Whisper `base` detects the language of every speech region, Whisper
`small` transcribes each language run with word timings (on the NVIDIA card when its libraries work, else the
processor — `transcribe.gpu_error` fallback) (each region gets one of the video's languages,
`transcribe.video_languages`; runs keep up to 1 s around them) → sentence lines (`segments.split_into_units`) → 3. Translate
(`translate.Translator`): lines already in the dub language kept; Claude (opt-in key) gets the whole video with time
slots, else one-language batches to Google (retries 2-4-8-16-30 s); fallback chain Claude → Google → NLLB-200 1.3B
offline; quality gate → 4. TTS twice (measure, then planned Edge `rate`,
`timing.plan_rates`) → 5. Align (trim Edge silence, lines on the speaker's start times, ≤1.1× correction) → 6. Mux
(language tags) + subtitles + meta. Optional before 6: `separate.py` (Demucs ONNX) removes the
original voice; the voice-free background goes under the dub, ducked while it speaks. «Оригинал» (`clone.py`,
NVIDIA only): voice split off first → `speakers.assign` (who says each line) → OmniVoice speaks each line in its
speaker's voice (one ≤10-s sample per speaker, ≤1.25× their pace, ≥ `clone.min_seconds`), Whisper listens to every
clip (garbled → up to 3 tries) → align lets different speakers overlap; lines fade in/out (ADR-036…040).

## What works (verified by running it)
- **0.10.3–0.11.0 (session 9, ADR-036…040):** unit tests for every piece (213); real OmniVoice + real Whisper on the
  sandbox CPU: the speed table (RESEARCH "how fast can a line be asked for"), the listen-back loop, and speakers +
  per-speaker references end to end on a 3-voice test (7/8 lines exact); the voice-print model on that test (all
  lines right, RESEARCH "Who speaks each line"); Chromium: library/watch page with dates + times RU/EN, 360–1280 px.
  Adam (by ear, 2026-10-29): 0.10.3 "a lot better", 0.10.4 "better" — but rough edges, which 0.11.0 addresses.
- **0.10.2 (ADR-035):** unit tests (card check ok / "no kernel image" / cached / non-blocking, `clone:no_gpu`,
  voice-free background, install progress from bytes checked against a real pip log, `tts_clone` estimate,
  logged-out login files refused); Chromium on the stub server (progress bar RU/EN, Settings card line with
  `STUB_CUDA=broken`, the locked switch) + QA agents' fixes re-checked (phone 360×640, desktop 1366).
- **0.10.1 (ADR-034):** the cublas failure reproduced with a stand-in Whisper and fixed (test); NVIDIA wheels resolve
  on Windows CI.
- **0.10.0 phone version (ADR-033):** Worker Node tests; PC side unit tests (token, routes, CORS, bridge); Windows CI
  runs a real cloudflared tunnel (401 without the token, 200 with it); end-to-end in Chromium with the local
  stand-in (pairing, PC on → dub, library/video/download through the tunnel, PC off → queued → PC back → dubbed,
  share target, paste, offline app, Samsung/iPhone sizes, RU/EN, dark).
- **0.9.0 (TikTok/Instagram/Facebook, ADR-031/032, PR #14):** unit tests with a yt-dlp stand-in (HEVC → H.264, ids,
  login file merge/summary, API, error texts incl. Instagram's anonymous rate limit); yt-dlp lists curl_cffi
  impersonation targets (test + Windows CI step); the «Вход на сайты» panel in Chromium on the stub server (RU/EN,
  1280/360 px, dark). **No real download from these sites yet** — the sandbox can't reach them.
- **0.8.0 (PR #13):** Windows CI: install without winget in a folder with a Russian name, venv from a too-new Python
  rebuilt, Whisper model in a Russian-named folder, component repair; on-screen subtitles in Chromium (RU/EN,
  1280/360 px, dark, Hebrew + English lines, CC-menu sync). Not yet on a real Windows 11 PC.
- **0.7.0 — the original voice «Оригинал» (ADR-028, `clone.py`):** unit tests with a stand-in model; the Settings
  panel, install progress, the third voice option, Hebrew hint and job-card step order in Chromium on the stub server
  (RU/EN, 1280/360 px, dark, with/without a GPU); a real end-to-end dub of a 2-speaker clip on **CPU** with the real
  OmniVoice (see PROGRESS). Not seen on a real NVIDIA card yet.
- **0.6.1:** Windows CI: a program started without the launcher (as after a self-update) makes the desktop shortcut
  itself; the console-font helper compiles and runs in Windows PowerShell 5.1. Adam: 0.6.0 self-updated on his PC.
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
- **0.11.0 by ear on Adam's RTX 5060 Ti:** speakers right? one voice per person? soft edges? overlaps natural? the
  12-lines-per-call speed. (Since 0.10.2 «Оригинал» runs on his card — he saw ~50% GPU load; the voice copy is
  "good".)
- **Phone version (0.10.0):** a real quick tunnel and the real Worker (blocked here; the Windows CI step runs real
  cloudflared through a real tunnel), a real Samsung / iPhone (install, share target, paste, video playback). Needs
  Adam's Cloudflare account first.
- **Real TikTok / Instagram / Facebook links (0.9.0)** — public ones should work without a login (ADR-032); whether
  Instagram's anonymous path holds up in practice is the big unknown. If it fails often → offer the in-program login
  window (RESEARCH option 5, ADR-032 "Next").
- **0.8.0 on a real Windows 11 PC** (father's): fresh install, the C++ runtime prompt, subtitles with both switches.
- Earlier items were all verified by Adam on 2026-10-19 (0.6.1, clean-PC install, playlists, uploads, Claude dubs,
  voice removal, Google, H.264 playback).

## Next steps (in order)
0. **Adam re-dubs with 0.11.0 and listens** (the same Men-in-Black scene, «Оригинал», background on): each person one
   voice? soft line edges? interruptions natural? the window's «Голоса: в видео говорят N» right? Useful from him:
   that line, «проверено на слух … неразборчиво осталось N», total time, `timing.json` (lines carry `speaker`) and
   `work/<id>/clips_original_ru/check.json` (text only — fine to share; never the audio/video of third-party films).
1. **Asked by Adam for next (2026-10-30) — not started:**
   a. **One library card per dub** (`kanban/library-card-per-dub.md`): today a video's dubs share one card (ADR-027,
      his earlier choice); now each dub — even a repeat with the same settings — gets its own card with its date and
      time. Keep search; decide what the watch page's «Другие озвучки этого видео» shows (keep it). Update guides.
   b. **«Оригинал» weak points** (`kanban/original-voice-quality.md`): one-word lines ("Да.") babble after 3 tries;
      foreign speech in the original (e.g. Spanish in an English film) misheard by Whisper and transliterated by Claude
      into nonsense; true crosstalk missing from Whisper's text.
   c. **American accent in the Russian dub** (same card): the copied voice carries the English reference's accent
      (cross-lingual cloning). Research first, then propose to Adam — see the card for candidate approaches.
2. **Switch the phone version on:** Adam (a) creates a free Cloudflare account, opens "Workers & Pages" once (choose
   the `workers.dev` name), makes an API token from the template "Edit Cloudflare Workers" and adds GitHub secrets
   `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`; (b) sends the address `https://dubber.<name>.workers.dev` →
   set `phone.MAILBOX_URL` in a small PR (until then «Телефон» says "not switched on yet"); (c) merge →
   `deploy-phone.yml` deploys (check its log: KV namespace made, `wrangler deploy` ok); (d) he pairs his Samsung
   (QR), dubs with the PC on and off; an iPhone if at hand. If quick tunnels prove flaky → named tunnel (ADR-033
   "Risks").
3. **Real TikTok / Instagram Reel / Facebook links without a login** (0.9.0): ask what the job card said for any
   failure; login-only → «Вход на сайты»; rate limit → wait an hour; Instagram often failing → propose the
   in-program login window (ADR-032 "Next") — ask first.
4. **Father's Windows 11 PC:** fresh install (Visual C++ prompt → «Да»), a dub with both subtitle switches
   (`kanban/install-and-subtitles.md`). His RTX 3050 has 4 GB — no «Оригинал» there, but 0.10.1's Whisper-on-card
   applies.
5. QA leftovers (`kanban/nice-to-haves.md`, 2026-10-29): own dialogs instead of confirm(), accent-insensitive search,
   remember voice/background choices, confirm before per-video «Очистить кэш», offline banner on the PC, glossary
   validation, playlist-cancel keeps the other links, re-check the Haiku price in `translate.py`, Cyrillic voice names.
6. Ideas not yet chosen (offer, don't build unasked): voice speed control; 16 generation steps for «Оригинал» (≈2× faster, quality risk); Demucs on the card; Hebrew spelling fix on the free path
   (PLAN M7); offline TTS fallback (Silero); Telegram bot; ElevenLabs (paid); slight video slow-down (`kanban/voicestudio-omnivoice.md`).
7. Known limits: Hebrew homographs and grammatical gender (לך) can't be read right from plain text by any voice;
   speaker gender unknown to the translator; offline-backup slips (Hebrew "flour" → "acid/vinegar").

## Gotchas for Claude in the cloud sandbox
- **Testing the real «Оригинал» models here (CPU, no NVIDIA):** `download.pytorch.org` is blocked — make a scratch
  venv (not the repo's `.venv`) and `pip install torch torchaudio omnivoice==0.2.1 faster-whisper edge-tts
  sherpa-onnx` from PyPI (~6.5 GB; CUDA wheels run on the CPU). Append `/root/.ccr/ca-bundle.crt` to that venv's
  `certifi` bundle, else edge-tts fails with CERTIFICATE_VERIFY_FAILED (it uses certifi). `en-US-GuyNeural` once
  returned NoAudioReceived — `en-US-AndrewNeural` worked. Run with `DUBBER_CLONE_DEVICE=cpu HF_HUB_DISABLE_XET=1` and
  `python -I` + `sys.path.insert(0, repo)`; OmniVoice takes ~70 s per line on 4 cores (32 steps), so test 3–8 lines in
  the background and watch with Monitor. A reference's text must be what is said in it (a placeholder text made the
  model speak it: "Turn. Buy."). faster-whisper 1.2 + av 19: pass samples, not a file path. Test conversations: Edge
  voices of different speakers mixed with numpy (session 9 scripts lived in the scratchpad, not the repo).
- **New Python releases break installs:** components without a build for the newest Python fail as "No matching
  distribution found for onnxruntime". The launchers accept only 3.10–3.14 (ADR-029); check wheels with
  `pip install --dry-run --target X --platform win_amd64 --python-version 3.N --only-binary=:all: -e .`-style
  resolution before raising the limit.
- **Playwright's Chromium** is now at `/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` (the path changes with
  the image: `ls /opt/pw-browsers`).
- **Network:** the environment needs these hosts allowed (or "Full" access): `youtube.com`, `*.youtube.com`,
  `*.googlevideo.com`, `*.ytimg.com`, `youtubei.googleapis.com`, `huggingface.co`, `*.huggingface.co`, `*.hf.co`,
  `translate.googleapis.com`, `speech.platform.bing.com`. Fonts load from Google Fonts (optional).
- **Phone version without Cloudflare:** `python3 cloud/build.py`, `node tools/phone_dev.mjs 7871` (mailbox :8787 +
  "tunnel" :7872 adding Cf-Ray), then `STUB_MAILBOX=http://127.0.0.1:8787 STUB_TUNNEL=http://127.0.0.1:7872
  STUB_PULL=3 .venv/bin/python tools/stub_server.py DIR 7871`; the phone app is `/api/phone` → `pair_url`. Phone
  viewports in Playwright: `devices['Galaxy S9+']`, `devices['iPhone 13']`. Running downloaded binaries (cloudflared)
  is blocked here (the auto-mode classifier refuses "code from external"), and so is a force-push: when restarting
  the session branch from `main` after a merge, a plain fast-forward push works (the old tip is in `main`). Worker
  tests: `node --test cloud/worker/worker.test.mjs`.
- **NVIDIA / «Оригинал» without a card:** the stub server fakes the card check (`STUB_CUDA=broken` for the failure
  path) and the install (`STUB_GPU`, `STUB_CLONE_FAIL`); `clone.cuda_ok` / `gpu.wanted` are monkeypatched in tests.
- **QA agents:** spawning `general-purpose` agents with the `webapp-testing` / `web-design-guidelines` skills worked
  well (session 8d) — give each its own stub port and scratch folder, tell them not to edit the repo.
- **TikTok, Instagram and Facebook are unreachable from the sandbox** (network policy; they also block datacenter
  IPs): test with the yt-dlp stand-in in `tests/test_download.py`; real links only on Adam's PC.
- **Always install/upgrade `yt-dlp[default,curl-cffi]`, never plain `yt-dlp`:** without curl_cffi TikTok and
  Instagram refuse every download that has no login (ADR-032). `dubber.deps` reports the extra as missing.
- **YouTube blocks datacenter IPs** ("Sign in to confirm you're not a bot", then 403). For a real YouTube test, Adam
  must provide a fresh `cookies.txt`, stored **outside the repo** and passed via `DUBBER_COOKIES`. Never commit cookies.
  Without it, test with local files (`tools/qa_languages.py` makes multilingual clips with Edge voices).
- **Google Translate answers HTTP 429** from here → the `Translator` waits ~1 min, then uses the NLLB backup (the
  log says "unavailable … using the offline translator"). For quick runs pass `translator="offline"`.
- **Models downloaded on first use** (Hugging Face, cached in `~/.cache/huggingface`): Whisper `small` (~480 MB) and
  `base` (~140 MB); NLLB-200 1.3B int8 (~1.4 GB) only when the offline backup is needed.
- **Headless Chromium has no H.264.** For real playback make a VP9 copy:
  `ffmpeg -t 70 -i dubbed.mp4 -map 0:v:0 -map 0:a:0 -c:v libvpx-vp9 -b:v 300k -deadline realtime -cpu-used 8 -c:a libopus out.mp4`.
- **Playwright:** the venv has no playwright. Use Node: `npm i playwright@1.56.1` in a scratchpad folder and launch
  with `executablePath: "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"`; never run `playwright install`.
  `setInputFiles` with a non-ASCII file *path* fires no change event — pass `{name, mimeType, buffer}` instead.
- **Windows:** there is none here. Parse/compile `dubber.ps1` with PowerShell 7 for Linux (release tarball from
  GitHub into the scratchpad). The only real Windows is the `Windows install` CI job — read its logs with the GitHub
  MCP tools (`actions_list`, `get_job_logs`). GitHub saves workflow `run:` steps without a BOM, so Windows
  PowerShell 5.1 misreads Cyrillic typed there: build such strings from char codes. CI has no visible console, so
  how text *renders* (fonts) can only be checked on Adam's PC.
- **Patch scripts:** a Python script that does several `assert`-guarded replacements stops at the first miss —
  the earlier replacements are already written; re-run only the rest.
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
# card; settings kept in the data folder; a Claude key ending in "bad" is refused; playlists are faked: 3 videos,
# 15 when the list id starts with "BIG"; STUB_UPDATE=9.9.9 shows the update banner)
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
README guides: after changing a UI label in `i18n.js`, grep the README (RU + HE guides quote RU and EN labels) and
`docs/README.ru.md` for the old wording.

Check results with `ffprobe` (expect h264 + aac in the dub language + the original audio + mov_text in the dub
language; `mul` for a mixed-language original) and `output/<id>/timing.json` (late_lines, rates).
