# Progress log

Newest entries at the top. One entry per working session / milestone.

## 2026-10-29 — Session 9c: who speaks, two voices at once, soft edges, every dub its own entry (v0.11.0)
- Adam merged 0.10.4 (PR #19): "better", sent `check.json`; "very rough chops between sentences, harsh on the ear";
  asked to build the speaker proposal (who speaks, overlap, one sample per speaker); and (as asked at the start of the
  project) every dub its own library entry with the exact time, even the same video with the same settings.
- Built: `speakers.py` (CAM++ voice prints of Whisper's lines, grouped — ADR-038, measured in RESEARCH), per-speaker
  references (`clone.speaker_references`), per-speaker placement (`align.build_track(speakers=)`); soft line edges +
  smoother ducking (ADR-040); timestamped dub ids, date + time in the library/watch page/other dubs (ADR-039); guides
  RU/HE + README.ru updated.
- Verified: 213 tests; the real voice-print model on a 3-voice test conversation (all lines right); real OmniVoice +
  Whisper end to end with speakers on CPU; Chromium: library/watch page RU/EN, 360-1280 px (a long other-dub label
  overflowed a 390-px phone — fixed). Not verified: by ear on Adam's PC.
- Seen in Adam's `check.json`: lines Claude transliterated from misheard Spanish ("Йо, хани, че…") stay unclear; "Да."
  came out as babble after 3 tries — OmniVoice is weak on one-word lines (next idea: say them with a neighbour).

## 2026-10-29 — Session 9b: «Оригинал» listens to itself; names in Russian letters (v0.10.4, ADR-037)
- Adam merged 0.10.3 (PR #18): "a lot better", but sentences still cut off, some words left in English or said as
  the English word in the copied voice; asked for two dubbed voices at once when two people talk.
- Found: the Claude prompt kept names/acronyms "as in the original" (Latin letters → read in English). Measured the
  real OmniVoice on CPU (RESEARCH "how fast can a line be asked for"): one line garbled at −7% of its own length while
  others held at 8 syllables/s — slips are word-dependent and random, so a speed limit alone can't stop them.
- Built: prompt v3 (every word in the dub language's letters), `clone.MAX_RATE` 1.25, the listen-back check
  (`transcribe.reader` + `clone.heard_share`, up to 3 tries, the last at the voice's own pace, `check.json`).
- Verified: 205 tests; the real OmniVoice + real Whisper listener end to end on CPU (see ADR-037). Not built: two
  voices at once — proposal (speaker grouping) waiting for Adam.

## 2026-10-29 — Session 9: «Оригинал» swallowed words, card at 50% (v0.10.3, ADR-036)
- PR #17 (0.10.2) merged. Adam on the RTX 5060 Ti: the voice copy works and runs on the card (~50% load); but no
  background music, and sentences "swallowed or warped"; asked whether Claude Opus causes it (no — it only
  translates text). His `meta.json`/`timing.json`: `"background": false` (the switch was off for that job); lines
  spoken in 0.14–0.26 s with seconds of room, stretches planned at 1.6×.
- Built: a per-line speed floor (`clone.min_seconds`, syllables at most 7/s), groups sized by the card's memory
  (`clone.batch_for`), longest lines first, a failing group halved; rates in `timing.json` = what was asked.
- Verified: 199 tests (5 new: syllables, the floor, length grouping, batch from memory, halving). Not verified: the
  real card.

## 2026-10-29 — Session 8d: «Оригинал» on a real card, install progress, QA pass (v0.10.2, ADR-035)
- Adam merged 0.10.1. On his RTX 5060 Ti PC a 5-min «Оригинал» dub estimated 90 min with the card looking idle. He
  asked: a progress bar for the voice studio install; whether the background switches should be on with «Оригинал»;
  QA agents on the site.
- Built: real card check (`clone.cuda_status`, Settings line + «Установить ещё раз»), no CPU crawl (`clone:no_gpu`
  → Edge voice), device/timing lines in the program window, `tts_clone` ETA share, voice-free background always with
  «Оригинал» (switch shown on + locked), install progress bar from downloaded bytes.
- QA: two agents (desktop functional with `webapp-testing`; phone mode + `web-design-guidelines`). Phone findings
  fixed: library/watch said "empty"/"not found" while the PC was off, a link sent as the PC dropped was lost,
  identical queue labels, placeholder scrolled sideways after clearing, plurals, no visible "sent" note, form below
  the fold on small phones, no Android install hint, the whole bar as a live region, focus lost after «Убрать», a
  heading out of order, tap targets < 44 px (touch screens), «Готово» green 3.45:1 → 5:1, 13 px subtitles on phones.
- Desktop findings fixed: a logged-out cookies file was "added" (now refused, and it no longer replaces a saved
  login), the remove-voice choice was lost around «Оригинал», links inside other text («Посмотри https://…») are
  taken out, the background hint contradicted the remove-voice one, "work is kept" on a job cancelled in the queue,
  "other dubs stay" with no other dubs, the Settings intro, an EN label quote; the stub now fakes the card check.
- Left for later (`kanban/nice-to-haves.md`): native confirm() dialogs, accent-folding search, remembering the
  voice/background choices, a confirm on per-video «Очистить кэш», an offline banner on the PC, glossary validation,
  playlist-cancel dropping the other links, the Haiku price in `translate.py` to re-check, voice names in Cyrillic.
- Verified: 194 tests; browser checks of the bar, the Settings card line (ok/broken stub), the locked switch, the
  phone fixes (360×640) and the desktop fixes. Not verified: a real NVIDIA card.

## 2026-10-29 — Session 8c: NVIDIA PCs (v0.10.1, ADR-034)
- Adam merged PR #15 (0.10.0) and dubbed an Instagram reel on a new PC: the download worked, then «cublas64_12.dll is
  not found» — Whisper picked the NVIDIA card without NVIDIA's libraries. Reproduced with a stand-in model (test
  first), fixed: CPU fallback, background install of `nvidia-cublas-cu12` + `nvidia-cudnn-cu12` on Windows NVIDIA
  PCs (`dubber/gpu.py`), DLL folders on the search path, clear error text. Branch restarted from main; new PR.

## 2026-10-28 — Session 8b: phone version (v0.10.0, ADR-033)
- Adam: same flow as on the PC (scroll TikTok/Instagram/Facebook/YouTube, copy, paste into Dubber on the phone);
  Samsung for both, iPhone must work; anywhere; dub at once if the PC is on, else send-and-forget; home-screen icon;
  install as simple as possible (one click, the install fetches what's needed) → Tailscale dropped for a Cloudflare
  quick tunnel (no account) + a mailbox Worker on Adam's account.
- Built: `dubber/phone.py` (token, cloudflared download, tunnel, mailbox client, `PhoneBridge`), app.py tunnel gate
  (token, `PHONE_ROUTES`, CORS, `/api/phone`, QR via `segno`), `cloud/worker/` (Worker + KV + Node tests),
  `cloud/build.py`, `deploy-phone.yml`, phone mode in `app.js` (PC on/off bar, mailbox queue, paste, share target,
  install prompt, iPhone hint, media through the tunnel with the token), manifest + service worker + icons
  (`tools/make_phone_icons.js`), Settings → «Телефон» with the QR code, `tools/phone_dev.mjs` (local Cloudflare
  stand-in) + stub server hook, Windows CI step (real cloudflared + tunnel: 401 without the token, 200 with it),
  worker tests in CI. Guides RU/HE (section 9), README.ru, changelog.
- Verified here: 182 Python + 5 Node tests; end-to-end in Chromium (Samsung/iPhone sizes, RU/EN, dark) with the
  stand-in: pairing, dub with the PC on, library/video/download through the tunnel, PC off → queued → PC back →
  dubbed in the chosen language, share target, paste, offline app shell. Found and fixed on the way: the QR SVG had
  no xmlns (blank image), a restarted PC made a new token when its .env was not loaded, the full "What's new"
  history popped up on the phone.
- Waiting for Adam: Cloudflare account + secrets + the workers.dev address (then `phone.MAILBOX_URL`).
- CI: the Windows pytest run (in "Original voice install") failed on a phone test that assumed `/` in paths; fixed.
  The Windows tunnel step was green: real cloudflared, 401 without the token, 200 with it.

## 2026-10-28 — Session 8: phone version
- Adam merged PR #14 (0.9.0). He: the Settings window is squeezed — fix it and check it on a PC; then start the phone
  version.
- Cause: the panels were a 760 px column on the left of the 1120 px page. Now two columns from 1000 px (Claude,
  glossary, disk space | site logins, original voice), one column below with disk space last; site tiles 4 in a row
  or 2×2 (container query) — never 3+1.
- Verified in Chromium on the stub server: 1920/1366/1280/1024/900/600/360 px, RU/EN, light/dark, no horizontal
  scroll; 162 tests pass. **Adam: no two columns — keep the single 760 px column as before** (unchanged since #12) →
  reverted, no 0.9.1 release.

## 2026-10-28 — Session 7c: TikTok, Instagram, Facebook without a login (still v0.9.0, PR #14)
- Adam: the extension + cookies file is too much work for the user — find a way without a login; then make the docs
  ready for the next session.
- Research (`docs/RESEARCH.md` → "TikTok, Instagram, Facebook without a login"): yt-dlp's Instagram extractor sends
  its logged-out GraphQL query only when browser impersonation (curl_cffi) is available, and TikTok answers a
  bot-challenge page without it; a yt-dlp maintainer confirmed it in issue 17074. Rejected: third-party download
  sites, public/self-hosted cobalt, reading Chrome/Edge cookies (app-bound encryption). Kept for later: an
  in-program login window (Edge with its own profile + DevTools protocol).
- Built (ADR-032): dependency `yt-dlp[default,curl-cffi]` everywhere yt-dlp is installed or refreshed;
  `dubber.deps` also checks the extras' packages (PCs from before get curl_cffi on the next start); message for
  Instagram's anonymous rate limit; «Вход на сайты» text: usually no login needed, guide folded under "if a video
  won't download"; guides RU/HE + README.ru; Windows CI checks yt-dlp lists curl_cffi targets.
- Verified here: curl_cffi wheels for Windows 3.10–3.14; `yt-dlp --list-impersonate-targets` shows curl_cffi;
  162 tests pass. Not verified: live downloads (sites unreachable from the sandbox).
- Hand-off docs brought up to date: STATUS (state, not-verified list, next steps, gotchas), `kanban/next-steps.md`
  rewritten, CLAUDE.md + `dubber-pipeline` skill (curl-cffi rule, sites).

## 2026-10-28 — Session 7b: TikTok, Instagram, Facebook (v0.9.0)
- Adam merged PR #13 (0.8.0). Next: dubbing from Facebook/Instagram/TikTok. His choices: logins via a cookies file in
  Settings; he and his father use Chrome and Edge.
- `dubber/sites.py` (sites, folder-safe ids, cookies parse/merge/summary incl. JSON exports), `/api/cookies`,
  Settings panel «Вход на сайты» with a Chrome/Edge guide ("Get cookies.txt LOCALLY"), login/private/unsupported
  error messages, H.264 preferred for combined formats and HEVC re-encoded (`media.to_h264`, also for uploads),
  uploader as channel, hero text names the sites (ADR-031).
- Verified: unit tests (yt-dlp stand-in "downloading" a real HEVC clip → H.264 with sound, nothing left behind;
  uploaded HEVC .mov converted, original untouched; merge/summary/JSON; API add/merge/reject/Origin/remove; error
  texts). Chromium on the stub server: add a bad file (message), add Instagram+TikTok (badge «Входов: 2», expiry
  date), remove; RU/EN, 1280/360 px, dark — fixed a class clash (`.steps` = the job card's steps) found there.
  Not verified: real TikTok/Instagram/Facebook links (the sandbox can't reach them).

## 2026-10-28 — Session 7: Windows 11 install audit + on-screen subtitles (v0.8.0)
- Adam: father's PC has an RTX 3050 (4 GB) — too small for «Оригинал»; he'll try it on his own PC later. He hit "some
  package was missing" installing a few days ago.
- Install audit: Windows wheels exist for every component on Python 3.10–3.14 (resolved with `pip --platform
  win_amd64`); onnxruntime and ctranslate2 import `MSVCP140.dll`/`MSVCP140_1.dll`, which Python doesn't bring and
  the CI image already has → a fresh PC could fail every dub. Launcher now: C++ runtime check (14.40+) + install,
  direct downloads when winget is missing, 64-bit Python only, broken venv rebuilt, too-deep folder reported,
  `dubber/deps.py` check + repair at every start, local `ffmpeg/` on PATH (`config.use_local_ffmpeg`). New CI job
  `clean-pc` (no winget, Cyrillic folder, Whisper model in a Cyrillic folder, repair after removing a component).
- The Windows CI reproduced an install failure: pip on Windows "No matching distribution found for
  onnxruntime>=1.17 (from versions: none)" while the index lists Windows wheels (ADR-029).
- On-screen subtitles: two switches under the player (dub language / original), one browser-drawn text track,
  dub line timed by the dub voice (`spoken` from `timing.json`), both lines in one cue (dub on top), bidi isolates
  (ADR-030). Chromium: RU/EN, 1280/360 px, dark, Hebrew + English lines, CC-menu sync, no console errors.
- Future work cards (Adam): phone version (`kanban/phone-app.md`), Facebook/Instagram/TikTok
  (`kanban/more-video-sites.md`).

## 2026-10-19 — Session 6b: the original voice «Оригинал» (v0.7.0)
- Adam: his father's PC has an RTX 3070 (8 GB) + i7-11700 → build an opt-in OmniVoice voice with a "only for such PCs"
  warning. His choices: each speaker's own voice, Edge for Hebrew, install from the Settings page (ADR-028).
- Built `dubber/clone.py` (nvidia-smi check, background installer: CUDA PyTorch + `omnivoice==0.2.1` + CUDA check and
  model download; per-line references from the Demucs vocals; length per line from the model's estimate →
  `timing.plan_rates` → `duration=`; batches of 4, one-by-one retry; clips levelled), `separate.py` also writes the
  vocals, pipeline voice `"original"` (separation before TTS, Edge male fallback + `voice_notes`), app `/api/clone`,
  Settings panel + third voice option + job-card step «Голос диктора», stub server stand-ins, Windows CI job that runs
  the install commands (`original-voice-install.yml`).
- **Real end-to-end dub on CPU** (2-speaker 17-s clip: Edge Andrew + Ava, quiet tone; Whisper, Demucs, NLLB offline,
  real OmniVoice): 436 s, of which OmniVoice ~330 s (7 lines). Each line copied its own speaker (pitch: male lines
  94–121 Hz, female 176–211 Hz); all 7 lines transcribed back correctly. **Found and fixed:** OmniVoice's length
  estimate boosts short lines (≤ 2 s) up to 2.5× → the planned pace came out 1.52× and the dub ended long before the
  speaker; with the unboosted estimate the pace is 1.02× and every line lasts about as long as the speaker's
  (2.94 vs 2.98 s, 2.93 vs 3.24 s, 1.57 vs 1.74 s), no late or stretched lines.
- The new Windows CI job ran the test suite on Windows for the first time: both install steps worked (CUDA PyTorch +
  omnivoice); 2 tests failed reading ffprobe's JSON in the Windows code page (the «Русский» track title is UTF-8, byte
  0x81 is undefined in cp1252). `media.run_ffmpeg`/`probe`, `clone.gpu_info` and the tests now decode UTF-8 — a
  Russian title in a user's video could have broken `media.probe` on Windows the same way.
- Browser (Chromium, stub server): install flow, the «Оригинал» option and Hebrew hint, step order with the voice split
  first, RU/EN, 1280/360 px, dark, PC without NVIDIA — no console errors. Not seen on a real NVIDIA card (none here).

## 2026-10-19 — Session 6: research VoiceStudio / OmniVoice (voice cloning)
- Adam verified every "not verified" item on his PCs (0.6.1 font + shortcut, clean-PC install, playlists, uploads,
  Claude dubs, voice removal, Google, H.264 playback) — STATUS updated.
- Adam asked to research [VoiceStudio](https://github.com/debpalash/voicestudio). Its core is the OmniVoice model
  (voice cloning, 646 languages, exact line length). Measured here on 4 CPU cores: ≈ 20× slower than real time
  (≈ 2 h of voice generation per 10-min video), batching doesn't help; Russian clear, Hebrew garbled. Proposal
  (ADR-028): optional "original voice" only on an NVIDIA GPU; plus three CPU-friendly ideas from its pipeline.
  Sandbox notes: `download.pytorch.org` is blocked (install torch from PyPI); edge-tts needs the proxy CA
  (`/root/.ccr/ca-bundle.crt`) patched into `edge_tts.communicate._SSL_CTX` in throwaway scripts.

## 2026-10-19 — Session 5 hand-off
- Hand-off docs brought up to date for the next session: STATUS (state, git, not verified, next steps, new sandbox
  gotchas: Node Playwright, PowerShell 7 on Linux, Windows only via CI, BOM-less workflow steps), `kanban/next-steps.md`
  rewritten, stale cards closed, new cards for 0.6.1 and the README guides, CLAUDE.md layout + README-guide rule,
  dubber-docs skill, PLAN ticks.

## 2026-10-18 — Session 5c: step-by-step guides in the README (Russian + Hebrew)
- Adam: a full, simple install-and-use guide for non-technical users in Russian and Hebrew on the README, committed
  straight to `main` at his request. Top of `README.md`: direct ZIP download link, unpacking, «Start Dubber», the
  Windows warnings (SmartScreen, security warning, UAC), first-run wait, daily use, closing, updates, a small
  troubleshooting table. The Hebrew guide is RTL and tells the reader to switch the site to EN (the site has no
  Hebrew interface) and quotes the English button names.
- Expanded both README guides to every function (Adam): site sections, several links / playlists / files, dub
  options, the job card, watching (transcript, subtitles, downloads, other dubs), library + search, Claude step by
  step (console account, billing, monthly limit, key, model prices from the app's own estimate, glossary), disk
  space, updates / What's new, tips, a larger troubleshooting table. Every quoted label checked against `i18n.js`
  and the server's messages.

## 2026-10-18 — Session 5b: question marks in the window (v0.6.1)
- Adam merged PR #9; after a restart the PC updated itself to 0.6.0. The shortcut appears once «Start Dubber» runs
  (the self-update restarts only the program, not the launcher). His screenshot of the launcher window: title
  «Дубляж видео» correct, every Russian line `?` — also Python's own output, so not an encoding problem but the
  console font (Raster Fonts have only the system language's letters). Fix: switch to Consolas at start (ADR-025
  follow-up). Not verifiable here or in CI (no visible console) — Adam checks.
- Adam: yes to the shortcut after a self-update. The program, when started on Windows without the launcher (the
  restart after a self-update, an old start file), runs `dubber.ps1 -ShortcutOnly` in the background; the launcher
  marks its own starts with `DUBBER_LAUNCHER=1`. CI starts the program directly and waits for the shortcut.

## 2026-10-18 — Session 5: one-click Windows start, upload, playlists, disk space, "What's new" (v0.6.0)
- Adam merged PR #8. Asked: fix the installer (question marks, no shortcut) so one click installs, creates a desktop
  shortcut with a dedicated icon and starts; then ideas 1 (upload), 2 (several links/playlists), 4 (What's new),
  5 (disk space), 8 (grouped library + search).
- **Windows start (ADR-025):** new CI job on `windows-latest` reproduced Adam's exact error ("Unable to save shortcut
  …?????? ?????.lnk"): WScript.Shell saves in the ANSI code page. Now `Start Dubber.cmd` (ASCII) runs
  `scripts/windows/dubber.ps1` (UTF-8 BOM, Russian text shows correctly), shortcut via IShellLinkW with
  `dubber/assets/dubber.ico` (site logo). CI green: install, existing install recognised, shortcuts + icon read
  back, the `.cmd` starts the program.
- **Upload / several links / playlists (ADR-026), grouped library + search, disk space, What's new (ADR-027)** —
  each tested in Chromium on the stub server (RU/EN, 360/1280 px); 9 new server tests (127 total).
- Found on the way: Playwright `setInputFiles` with a non-ASCII path fires no change event (tool quirk); the disk-space
  panel overflowed 360 px (fixed); old installs would have reinstalled everything (now recognised).
- **QA agent pass** over the new features, fixed: the same uploaded file dubbed twice (the first finished job deleted
  the file the second needed); users coming from 0.5.x would never see "What's new" (no stored version → now
  detected by their other settings / library); upload box overflowing 360 px and an invisible progress track; drop
  overlay under the form's controls; a file dropped outside the form opened in the tab; disk-space refusals shown in
  green; uploads counted in the cache without a row (now «Загруженные файлы…», clearable); duplicate links queued
  twice; playlists over 10 videos queue only after asking; Esc closes the playlist question, which also follows a
  RU/EN switch; big uploads no longer block the server while written.

## 2026-10-18 — Session 4c: trim personal details, full QA pass (v0.5.1)
- Adam: 0.5.0 works. Asked to trim the personal details about the end user (current files only; "Adam" stays as
  maintainer), to run the QA agents again over everything, and for ideas.
- Three QA agents: guideline audit (`web-design-guidelines`), hands-on Playwright tester (6 pages × RU/EN ×
  light/dark × 360/768/1280), code review of the session-4 code with reproductions.
- **Updater made safe to fail** (code review, reproduced): the version file is now written last, after the
  components installed — a failed pip or a locked file (Windows antivirus) leaves the old version, so the next start
  retries (`.dubber-deps` stamp reruns pip until it succeeded); file errors no longer stop the start; stray
  `.partial` files removed; ZIP names / manifest lines confined to the folder; one website update at a time and no
  new dub meanwhile; 3 s graceful shutdown on restart (open video streams); Ctrl+C doesn't kill the new version;
  unusual video ids of other sites get a safe library folder name. 5 new tests.
- **UI fixes:** update banner stuck on «Обновляю…» (never showed the restart note); dubs differing only in the
  background got identical labels (now «без фона»); delete dialog names the dub and says other dubs stay; footer
  aligned with content and consistent space below pages; no blue frame around the page after keyboard navigation;
  "г." no longer wraps alone; one term for voice removal («голос диктора»); hero tense; «Установить обновление»;
  window name «Дубляж видео»; EN "audio" everywhere; glossary example never splits; status role on the banner text
  only; labelled download / other-dubs groups; key error re-translated on RU/EN switch; job clock starts when the
  job leaves the queue (`started`); clearer "key too short" message; no unhandled `play()` rejection.
- Not changed (by design): `https://localhost` accepted (developer use); remove-voice switch keeps its state while
  disabled (ignored on submit); a pre-0.4.1 dub redone with identical choices shows twice (rare, old entries only).
- Verified in Chromium after the fixes (banner restart note RU/EN, labels, delete text, footer, focus). 118 tests.

## 2026-10-18 — Session 4b: the program updates itself (v0.5.0)
- Adam: the hosting question was really "stop downloading the ZIP after every merge". He will make the repo public
  and wants updates both at start and with a button.
- `dubber/update.py` + start-up update + `/api/update` + banner «Обновить» (ADR-024). Rehearsed with a fake GitHub
  on localhost and a separate install folder: 0.5.0 → 0.5.1 at start (Claude key and library kept, new version
  started), 0.5.1 → 0.5.2 with the button in Chromium (page reloaded on the new version). 11 new tests.
  Checked the whole git history before going public: no keys, tokens or e-mails.

## 2026-10-18 — Session 4: separate dubs in the library, Hugging Face hosting research (v0.4.1)
- Adam merged PR #6 and confirmed the dub quality. Asked: two dubs of one video both played the newest one; and
  research Hugging Face Spaces as hosting.
- **Library (ADR-022):** every dub has its own `output/<video-id>--<lang>-<hash>/` folder; the same choices again
  replace that dub; cards show language · voice; the watch page lists "Другие озвучки этого видео". Old library
  folders keep working. Verified: two real pipeline runs of one clip (ru, en) → two folders with the right audio
  language each (ffprobe); in Chromium (RU desktop, EN 360 px dark) each card plays its own file and the switcher
  goes to the other dub. 4 new tests.
- **Hosting (ADR-023, RESEARCH.md):** Spaces can run our app in Docker, but needs PRO ($9/month), a paid bucket for
  the library, and YouTube blocks its servers → not now; revisit with video-file upload.

## 2026-10-18 — Session 3: Hebrew voice, translation quality, voice removal (v0.4.0)
- Adam: 0.3.1 installs and runs (installer no longer stalls). Asked: Hebrew dub mispronounces, translation still
  off sometimes even with Opus, and voice removal (Demucs), off by default. Free only; test without his input.
- **Hebrew (ADR-019):** built a measurable test (gold IPA + stress, Hebrew-IPA Whisper scorer) — plain Edge is the
  best free option; niqqud makes Edge worse; Adam's "iter" comes from the spelling ייתר (Edge reads it right as
  יתר). Claude now gets Hebrew/Russian spelling notes for the speech engine. `tools/qa_hebrew_voice.py`.
- **Translation (ADR-021):** found two transcription bugs on real speech: stray language guesses (Hebrew regions
  transcribed as Italian/French) and first words lost at language switches — both fixed (mixed EN+FR errors
  0.199 → 0.153). Whisper turbo measured, not adopted. Claude request: topic, ASR-aware, sentence-aware, effort
  medium, prompt version in the cache key. No Claude key here: unit-tested only.
- **Voice removal (ADR-020):** Demucs v4 ONNX on CPU, switch on the website, CLI `--remove-voice`; verified: no
  words left in the background, music level unchanged, end-to-end dub with music + Russian voice; ≈ +5 min per
  10-min video. UI checked in Chromium (RU/EN, 360 px, dark).

## 2026-10-18 — Session 2f: installer "stuck after Obtaining file", hand-off docs
- Adam: the installer window seems stuck after "Obtaining file:///…". Not reproducible here (the step takes ~3 s; the
  editable build does not walk `work/`/`.venv`). The next hidden step is pip's build isolation (a temporary env that
  downloads setuptools, silent in plain output). Both installers now install `pip setuptools wheel` into `.venv`
  first, install Dubber with `--no-build-isolation`, and write a full `install.log` (git-ignored) to share if it
  stalls; the window says it can take 10–15 min the first time. Verified in a fresh venv (Linux).
- Adam's git rule: a new branch only for a new feature; fixes go on the current branch (CONTRIBUTING, CLAUDE.md).
- STATUS rewritten for the next session; kanban hand-off list refreshed.

## 2026-10-18 — Session 2e: old styles after updating (PR `fix/asset-versions`, v0.3.1)
- Adam updated to 0.3.0: first the old page opened; after a refresh the page was "broken" — new HTML with the old
  `styles.css`/`i18n.js` (huge gear, raw `nav.settings`). Reproduced exactly in Chromium (old `main` with 10-day-old
  files, then the new server, then a refresh): browsers re-check only the page on refresh and reuse saved files.
- Fix: the app serves `index.html` itself with versioned file addresses (`?v=<version>.<newest file time>`); verified
  the reproduction is fixed and that a simulated next release appears on the first open without refresh.
  Adam: Ctrl+F5 didn't help in Opera GX → README.ru says to clear cached files once (Ctrl+Shift+Delete) when
  updating from ≤ 0.3.0. 90 tests pass.

## 2026-10-17 — Session 2d: updates always visible + time left (PR `fix/updates-and-eta`, v0.3.0)
- Adam: after updating to `main` no Settings icon / model menu; wants a time-left timer.
- Cause (verified): starting the new version while the old window runs left the old server on port 7860 — the new
  one failed, the browser opened the old page. Also site files had no cache headers. Fix: start-up check ("already
  running (version …)", no browser, exit 1; browser opens only when this version answers), `Cache-Control: no-cache`
  for the site, version 0.3.0 in the footer and `/api/version`, update steps in README.ru.
- Time left (`dubber/eta.py`): stage timings + stage shares learned from this PC's last 10 dubs; shown as
  «≈ осталось N мин» next to the elapsed time. Checked against a stub job (estimate within ~1–3 s of the truth),
  RU/EN, 360 px (timers on their own row on phones).
- 89 tests pass (1 network test skipped).

## 2026-10-17 — Session 2c: Claude translation from the website (PR `feat/claude-translation`)
- Adam chose: key entered on the website, default model Opus 5.5, general-purpose glossary now, he reviews and merges.
- Settings page (gear in the header): key checked with a free call and saved to `.env` (only `…last4` shown), model
  with price, Claude on/off, glossary. Origin check on state-changing API requests.
- Claude gets the whole video with each line's language, time slot and character budget → dub-length lines; streams;
  errors (bad key, no credit, overload, refusal) fall back Claude → Google → offline with the reason on the watch
  page; cost per video in `meta.json`. Own cache per model + glossary. `anthropic` installed by default.
- Verified: 80 tests pass (1 network test skipped); Chromium flows in RU/EN, light/dark, 360/390/600/1280 px (no overflow; fixed a cut-off header,
  a collapsed key field and a truncated model menu on the way); real SDK with a dummy key → "key not accepted".
  Not run with a real key yet.
- Also: the stub server keeps its settings in its data folder (never the project's `.env`).

## 2026-10-17 — Session 2b: `main` and a professional git workflow
- Created `main` (from the session branch, which contains the old default branch). From now on: branch per piece of
  work → PR into `main` → CI green → Adam reviews and merges (`CONTRIBUTING.md`, PR template).
- CI: GitHub Actions `ci.yml` (Ubuntu, Python 3.12, ffmpeg, `ruff check .`, `pytest`).
- `dev-uploads/`: a drop box for files Adam wants Claude to read (uploaded on `uploads/…` branches via the GitHub
  website); its README lists the cache files needed for the translation/timing regression.

## 2026-10-17 — Session 2: Adam's feedback after the re-dub
- Adam: the EN+FR video now works, but translation quality and timing feel worse than before; Dubber will be
  used for every topic (general glossary, not a field list); target PC is Windows; still deciding on a Claude key.
- Bug: after dubbing a video into Russian and then into Hebrew, the watch page showed Hebrew text and voice name but
  played the Russian dub. Cause: `dubbed.mp4` keeps its URL and was served without cache headers, so Chrome reused its
  copy. Fix: the video URL carries a version (`?v=` from the file's mtime + size) and `/files/` answers
  `Cache-Control: no-cache`. Reproduced with the old code and verified fixed in Chromium (2-s dub replaced by a
  4-s one); test `test_redub_changes_video_url_and_files_are_revalidated`. 65 tests pass.
- Regression investigation opened (`kanban/translation-timing-regression.md`): needs the cache files from Adam's PC.

## 2026-10-17 — Session 1k: hand-off for the next session
- Adam will start the next session from `claude/inspiring-davinci-4qon8o` (the default branch is outdated).
- Rewrote `docs/STATUS.md` (state, how it works, verified, not verified, next steps, gotchas, how to test) and
  refreshed `CLAUDE.md`; kanban cleaned up (`kanban/next-steps.md` = open items); README.ru notes the offline backup.
- Moved the session's QA tooling into the repo: `tools/stub_server.py` (website with a stand-in pipeline) and
  `tools/qa_languages.py` (real dubs of 2 multilingual clips × 12 languages with translation/re-listen/timing checks;
  verified: trio → es, 0 untranslated, 99 % re-heard, 0 late lines).

## 2026-10-17 — Session 1j: every language translated correctly + 12-language QA
- Adam: in his EN+FR video the French was untranslated or gibberish; all languages must work like the Russian dub.
- Causes and fix: see ADR-016 and RESEARCH "Every dub language". Line languages (per-region detection), Google JSON
  client with retries, NLLB-200 1.3B offline backup for any pair, quality gate, versioned caches.
- QA harness (real Whisper/NLLB/Edge, 2 multilingual clips × 12 languages = 24 dubs): 0 untranslated lines, 0 late
  lines, dub re-heard by Whisper 93–100%, pace 0.90–1.60×. Bugs it caught and fixed: English after French labelled
  French (detection), Chinese lines cut at a comma (forced continuation), stray spaces before punctuation; plus a
  metric bug in the harness itself (difflib autojunk). Google could not be tested live here (429).
- 64 tests pass.

## 2026-10-16 — Session 1i: cancel, any language, RU/EN interface, agent QA
- Adam: dubbing "works great"; asked for a cancel button, any-language dubbing (his video had French in it), and an
  agent QA pass over the UX/UI with a QA skill.
- Cancel (ADR-015): queued jobs never start, running ones stop at the next progress report; cache kept → resume.
- Languages (ADR-014): measured that Whisper forced to English **dropped a French passage**, and auto-detect dropped
  the English intro. Now: language per stretch of speech, each run transcribed in its own language — verified on a
  real mixed EN/FR clip (all 11 sentences, correct languages). 12 dub languages with male/female Edge voices;
  Google auto-source; offline fallback en→ru only. Real full run EN/FR → Hebrew (Hebrew text supplied by hand because
  Google is blocked in the sandbox): Hila voice, pace 1.09×, all lines on time, tags heb/mul/heb.
- RU/EN interface (`dubber/web/i18n.js`), dub-language select, RTL transcript, bilingual server errors.
- QA skill: vendored Vercel `web-design-guidelines` (+ existing `webapp-testing`). Two agents: a guideline audit and a
  hands-on Playwright tester (107 screenshots, RU/EN, light/dark, 360–1280 px). Fixed: focus lost every second on job
  cards (cards now patched in place, live region for stage changes), skip link navigating to home, double submit,
  "Failed to fetch" raw errors, RU-only API errors, loose URL check, focus ring radius/contrast, switch contrast,
  invisible dark chevron, 360 px select/header overflow, job order (running first, compact queued cards), orphaned
  Delete button, download labels, ragged RTL transcript, step badge alignment, transcript = one tab stop with arrows,
  route focus, missing-page title, copy fixes (ё, EN wording). Not changed: native confirm() for delete.
- 62 tests pass.

## 2026-10-16 — Session 1h: "No audio was received" fix
- Adam's re-dub on his PC failed: edge-tts `NoAudioReceived`. (He also asked about hosting the site publicly on
  Vercel/Railway — explained Vercel can't run it and Railway would need paid hosting + YouTube cookies; he dropped it.)
- Reproduced: Edge returns no audio for text without letters ("…", "—", "♪", "?") every time, and **at random for
  normal text: 5 of 56 sequential requests (~9%)**. With per-sentence lines and two TTS passes (ADR-013) a long video
  sends hundreds of requests, so one line failing all 3 attempts killed the whole job.
- Fix: unspeakable lines get no clip (never sent); 6 attempts with backoff; a line failing at its planned rate uses its
  natural-speed clip; last resort one silent line (logged); job fails only if >20% of lines get no audio (outage), with
  a Russian message. Whisper non-speech words ("[Music]", "♪") no longer become lines.
- Verified: fresh real dub of the test talk (timing unchanged: 12 lines on time, pace 1.42×); real Edge run with
  "…"/"♪"/"—" lines. 52 tests pass.

## 2026-10-16 — Session 1g: dub timing implemented (free parts)
- Adam: "do everything that doesn't require payment" → M3.5 steps 1–5 (ADR-013).
- `segments.split_into_units` (sentence lines from word timestamps), `timing.py` (steady pace planner + Edge rate),
  two-pass TTS with clips keyed by text, `align.trim_silence` + ≤1.1× correction, `output/<id>/timing.json`.
- Found while testing: Edge pads every clip with ~0.25 s + ~0.9 s silence → lines started late and short lines
  looked huge to the planner. Fixed.
- Real run (synthetic English talk, real Whisper + Edge, offline translator): 12 sentence lines, all start on time,
  pace 1.40–1.50× with no time-stretching, 8/12 lines end within ±0.12 s of the speaker. Before/after table in
  `docs/RESEARCH.md`. 48 tests pass. Not yet heard on a real YouTube video (YouTube blocks this server).

## 2026-10-16 — Session 1f: dub timing research
- Adam: the dub works on his PC, but its pace doesn't follow the speaker (rushing / dragging).
- Measured on a synthetic English talk: Russian ≈ 1.47× English; nearly every line hits the 1.5× atempo cap; per-line
  speed jumps; Whisper units 4–11 s, cut mid-sentence. Verified Edge TTS `rate` scales duration exactly.
- Research (Amazon isochrony / prosodic alignment, LLM duration-budget translation, WhisperX/stable-ts timing) and a
  plan → `docs/RESEARCH.md` "Dub timing", `docs/PLAN.md` M3.5, `kanban/dub-timing.md`. Not implemented yet.

## 2026-10-16 — Session 1e: first Windows install
- Adam ran `install_windows.bat` on his PC: Python packages installed fine, but the desktop shortcut failed
  ("Unable to save shortcut ...\?????? ?????.lnk"), and the script still printed "Готово!".
- Cause: Windows PowerShell receives non-ASCII command-line text as `?`, and `?` is not allowed in file names.
  Fix: the name is built from char codes inside PowerShell, the folder path is passed through an env var, and a
  failure now says to use `scripts\start_windows.bat` instead of claiming success. Not yet re-run on Windows
  (no PowerShell in the sandbox).

- Second report: site started, first dub failed downloading the Whisper model from Hugging Face
  ("CAS Client Error ... error sending request for url https://us.aws.cdn.hf.co/xorbs/...") — the new Xet downloader.
  Fix: `HF_HUB_DISABLE_XET=1` by default (plain HTTPS; verified here: 483 MB `faster-whisper-small` downloaded),
  model downloads retried 3× (`dubber/hub.py`), a Russian message for model-download errors.
- The error card ran off the page (long URL in a grid item without `min-width: 0`). Fixed `.jobs` column + wrap long
  error text; checked in Chromium at 1280 and 390 px with the raw error: no horizontal scroll.
- 37 tests pass.

## 2026-10-16 — Session 1d: documentation handoff
- Added `docs/STATUS.md` (start-here page for future sessions), linked from `CLAUDE.md`; fixed stale Gradio/Haiku
  references in RESEARCH/PLAN/DECISIONS/kanban; ticked M3 items already done; new card `kanban/windows-install-test.md`.
- Explained to Adam how to install on his PC (branch `claude/bold-davinci-qfv627`, `scripts/install_windows.bat`).

## 2026-10-16 — Session 1c: professional website
- Adam: the user is a professional, not a beginner → modern product look. Researched design guidance and dubbing
  products; wrote `docs/DESIGN.md` (tokens, Onest + Unbounded fonts, cobalt accent, red "live" lamp, dark mode).
- Replaced Gradio with a FastAPI + hand-built site (`dubber/web/`): new-video page with live 6-step job card,
  library with thumbnails, watch page with player, RU/EN subtitles and a synced bilingual transcript.
- New option: dub without the original sound (Russian voice only; English kept as track 2).
- Output layout is now `output/<id>/` with `meta.json`, `thumbnail.jpg`, `segments.json`, `.vtt` subtitles.
- Bugs found while testing for real:
  - YouTube details were fetched even for cached videos → when YouTube refused (cookies expired/flagged), finished
    videos couldn't be rebuilt. Fix: id from the link + cached `info.json`. Test added.
  - Re-dubbing with another voice reused the first voice's cached clips (Svetlana job came out in Dmitry's voice).
    Fix: per-voice clip cache. Regression test; verified by pitch: Dmitry ≈ 113 Hz, Svetlana ≈ 179 Hz.
  - Transcript lines ran EN into RU; mobile nav wrapped. Fixed in CSS.
- Verified in Chromium: home/library/watch in light + dark + 390 px phone; a real job through the site; real playback
  (VP9 test copy, since test Chromium lacks H.264): play, click-to-seek, highlighted line, 25 RU subtitle cues.
- YouTube now refuses this cloud server even with the cookies (probably expired/flagged); not needed for the above.
- 34 tests pass.

## 2026-10-16 — Session 1b: real end-to-end test ✅
- Adam opened the network. Findings from real requests in the cloud sandbox:
  - YouTube: search + metadata work; **media download is refused** ("Sign in to confirm you're not a bot", then 403 on
    video data for every player client: mweb, web_embedded, web_safari, tv, android_vr). The browser-based PO-token
    plugin (yt-dlp-getpot-wpc) could not start a browser without a display. → Adam will provide `cookies.txt`.
  - yt-dlp now needs the **deno** JS runtime → added `deno` (pip) + `find_deno()`; works on Windows too.
  - Google Translate (both endpoints) answers this datacenter IP with a robot-check page.
    → Added **offline translator** (Helsinki-NLP opus-mt-en-ru, ONNX, ~110 MB, no torch) as automatic fallback.
    Quality: understandable, clearly below Google (e.g. literal phrasing, occasional wrong word).
  - edge-tts ignored HTTPS_PROXY (aiohttp) → pass proxy explicitly. Real Russian TTS now works.
  - Added `DUBBER_COOKIES` setting. 27 tests (1 network test with the real offline model, opt-in).
- **Real run 1 (CLI)** — TED-Ed "The science of spiciness" (3:55), Adam's cookies, Whisper small on CPU:
  - Bug: faster-whisper 1.2.1 crashes with PyAV 19 (`metadata_errors`). Fix: pass ffmpeg-decoded samples. Regression test.
  - Bug: offline translator stops after the first sentence of each input → 11 of 25 segments lost text.
    Fix: translate sentence by sentence. Tests (unit + network).
  - Fix: retries re-downloaded the video → look up the id first and reuse `work/<id>/`.
  - Speed-up: copy the English track instead of re-encoding (final step 32 s → 19 s).
  - Result: 234.36 s in → 234.36 s out; streams h264 + aac(rus, default) + aac(eng) + mov_text(rus); all 25 segments
    keep every sentence; every segment has Russian voice; Whisper listening to the dubbed track detects Russian
    (p=1.00) and 91 % of heard words match our translation. Time: ~3.8 min for a 3.9 min video (download 9 s,
    recognition 121 s, translation 40–53 s offline, voice 21–41 s, timing 5–8 s, assembly 19–32 s).
- **Real run 2 (web UI via Playwright)** — TED-Ed "What is imposter syndrome…" (4:19), female voice, every stage
  fresh: done in 250 s, "Скачать видео" downloaded a correct MP4, no browser console errors.
  - UX bug: for the whole run the page showed nothing (progress bar had no visible place). Fix: fixed-height status
    area + `show_progress="full"` → live bar "Озвучиваю по-русски – 63.7 %". Screenshots in `docs/images/`.
- Not verifiable here: in-page playback (headless Chromium lacks H.264), Windows installer, Google translation
  quality (Google blocks this server; a home connection should be fine).

## 2026-10-16 — Session 1: research, skills, foundation
- Agreed scope with Adam: runs on the user's PC, free-first, outputs = dubbed MP4 + RU subtitles + transcript.
- Researched existing dubbing projects and building blocks → `docs/RESEARCH.md`.
- Searched GitHub for Claude skills; cloned 11 repos, reviewed code, installed 12 skills → `docs/SKILLS.md`.
  Removed one auto-installing script from `youtube-downloader`; skipped two unlicensed skills.
- Wrote `CLAUDE.md`, plan, decisions, kanban board.
- M1: implemented the pipeline (`dubber/`): download, transcribe, translate (Google/Claude), tts, align, mux,
  subtitles, cached `pipeline.run`, CLI. 18 tests pass (`ruff` clean); offline e2e test builds a real MP4
  with 2 audio tracks + RU subtitles from a synthetic video using stubbed network services.
- **Blocked in the cloud sandbox:** network policy denies www.youtube.com, speech.platform.bing.com (edge-tts),
  translate.google.com, huggingface.co (Whisper models). Real end-to-end run pending (allow these domains or run on a PC).
- M2: Russian web UI (`dubber/app.py`, Gradio 6): link box, voice choice, live progress in Russian, video player
  with subtitles, 4 download buttons, history of earlier videos, Russian error messages. Verified in headless
  Chromium via Playwright (validation, full run, downloads visible, phone width, no console errors). Error popups
  show "Ошибка" on a Russian-locale browser. The headless test browser can't play H.264, so in-page playback was not
  verified here (normal Chrome/Edge play it).
- Installers: `scripts/install_windows.bat` (winget Python + ffmpeg, venv, desktop shortcut), `start_windows.bat`,
  `install.sh` / `start.sh`. Not yet tried on a real Windows PC.
- SessionStart hook (`.claude/hooks/session-start.sh`) installs deps in cloud sessions. 21 tests pass.
- Claude translation defaults to `claude-opus-5-5` (effort low, structured JSON output, server-side refusal fallback).
