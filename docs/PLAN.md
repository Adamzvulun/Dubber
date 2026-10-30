# Plan & roadmap

_Last updated: 2026-10-18 (session 3)_ — current state at a glance: `docs/STATUS.md`. Task cards: `kanban/`.

## Goal
A Russian speaker (not a developer) pastes a YouTube link into a local web page and gets:
1. the video dubbed into Russian (MP4),
2. Russian subtitles (SRT, also embedded in the MP4),
3. a Russian transcript (plus a bilingual EN/RU one for learning).

## Milestones
### M0 — Foundation
- [x] Research tools and existing projects → `docs/RESEARCH.md`
- [x] Decisions recorded → `docs/DECISIONS.md`
- [x] Find, review and install Claude skills → `docs/SKILLS.md`
- [x] Project skills: `dubber-pipeline`, `dubber-docs`, `ffmpeg-dubbing`
- [x] `CLAUDE.md`, `README.md`, `.gitignore`, `pyproject.toml`
- [x] SessionStart hook for cloud sessions (installs deps)

### M1 — Pipeline (CLI)
- [x] download (yt-dlp; local files also accepted)
- [x] transcribe (faster-whisper)
- [x] translate (Google free / Claude optional)
- [x] tts (edge-tts)
- [x] align (fit clips into timing, build Russian track)
- [x] mux (duck original, add Russian track + subtitles)
- [x] subtitles & transcripts
- [x] pipeline cache + CLI
- [x] unit tests + offline end-to-end test (network services stubbed)
- [x] real end-to-end run with YouTube + Whisper + translation + TTS (2 real TED-Ed videos, CLI + web UI; offline translator because Google blocks the cloud server)
- [x] offline translator fallback, cookies option, deno runtime
- [ ] real run with Google translation (needs a non-datacenter connection — first run on a home connection)

### M2 — Russian web UI + installers
- [x] ~~Gradio app in Russian~~ (first version; replaced by the custom website in M2.5)
- [x] Windows `install_windows.bat` / `start_windows.bat` (+ desktop shortcut); Linux/macOS `install.sh` / `start.sh`
- [x] Test the Windows installer on a real Windows PC (CI `windows-install.yml`, ADR-025; Adam runs it at home)
- [x] `docs/README.ru.md` user guide (Russian)
- [x] UI checked in Chromium with Playwright (desktop + phone width) → now `docs/images/site-home-*.png`

### M2.5 — Professional website (Adam's request)
- [x] Design research + design system → `docs/DESIGN.md`
- [x] Replace Gradio with a custom site: new video, library with thumbnails, watch page
- [x] Watch page: player with RU/EN subtitles + synced bilingual transcript (click a line to jump)
- [x] Live job card: 6 steps, progress, elapsed time; jobs survive closing the page
- [x] Option: dub without the original sound in the background
- [x] Light + dark mode, phone layout; verified in Chromium (incl. real playback with a VP9 copy)
- [ ] Verify H.264 playback in Chrome/Edge on a real PC
- [x] `main` branch + PR workflow + CI (lint + tests) + `dev-uploads/` (2026-10-17); Adam sets `main` as default

### M3 — Quality
- [x] Smarter timing: merge short segments into sentences before translating (`segments.merge_into_sentences`)
- [x] Glossary passed to the translator — general-purpose, edited on the Settings page, followed by Claude
  (ADR-017); the free engines can't follow one reliably
- [x] Voice choice (male/female) in the UI
- [ ] Voice speed in the UI
- [x] Optional Demucs: keep background music, remove the speaker's voice (ONNX on CPU, switch; ADR-020)
- [x] Translation prompt asks for "dub-length" Russian when using Claude (`translate.CLAUDE_SYSTEM_PROMPT`)

### M3.5 — Dub timing that follows the speaker (Adam's report, research in `docs/RESEARCH.md` "Dub timing")
- [x] Research + measurement of the current timing (RU ≈ 1.47× EN; every line at the 1.5× cap; speed jumps)
- [x] Word timestamps → sentence/phrase units with speech-only bounds; split long sentences at pauses
- [x] Steady per-video pace + smoothed per-line rate (narrow band)
- [x] Speed via Edge TTS `rate` (two-pass), `atempo` only as a small last correction
- [x] Use following pauses before speeding up; minimal push-back
- [x] Length-budgeted translation with Claude: per-line time slot + character budget (ADR-017)
- [x] Timing report in `output/<id>/` + tests for the timing planner
- [x] Trim the silence Edge puts around every clip (found while testing)
- [ ] Adam re-dubs a real video on his PC and listens

### M6 — Languages & polish (Adam, 2026-10-16)
- [x] Cancel button for a running/queued dub (ADR-015)
- [x] Any source language, incl. mixed videos — language detected per stretch of speech (ADR-014)
- [x] 12 dub languages, male/female voice each; language-coded outputs; old library still works
- [x] RU/EN interface switch; bilingual error messages; RTL transcript
- [x] QA skill (`web-design-guidelines`) + two QA agents over the whole UX/UI; fixes
- [x] Reliable translation for every language: line languages, Google retries, NLLB backup, quality gate (ADR-016)
- [x] 12-language QA: 2 multilingual clips × 12 dub languages, real pipeline (RESEARCH "Every dub language")
- [x] Real check on Adam's PC: re-dub the EN+FR video — every line now translated (2026-10-17)
- [x] Fix: after a re-dub into another language the watch page played the browser's cached old dub
- [ ] Adam: translation quality and timing feel worse than before the language work — investigate
  (`kanban/translation-timing-regression.md`; waiting for his files in `dev-uploads/`)
- [x] Claude translation from the website: key/model/glossary on a Settings page, whole-video context, dub-length
  lines, fallback chain Claude → Google → offline, cost on the watch page (ADR-017)
- [ ] Adam's first real dub with a Claude key (end-to-end check; compare timing with the free path)
  — Adam used it: "still off sometimes" → ADR-021 fixes; re-check with v0.4.0

### M7 — Session 3 (Adam, 2026-10-18)
- [x] Hebrew pronunciation measured; plain Edge kept; spelling notes for the speech engine (ADR-019)
- [x] Transcription: video-level languages, wider run margins; turbo measured, not adopted (ADR-021)
- [x] Claude request v2: topic, ASR-aware, sentence-aware, effort medium, prompt version in cache key (ADR-021)
- [x] Voice removal switch (Demucs ONNX) (ADR-020)
- [ ] Adam: re-dub a Hebrew video and an English one with Claude on v0.4.0 and listen
- [ ] Spelling fixes for the free path (Google/offline) if Hebrew misspellings show up there too
- [x] Updates always visible: no-cache site files, version in the footer, "already running" check (ADR-018)
- [x] Time left on the job card, learned from this PC's past dubs (ADR-018)
- [x] Versioned site file addresses so a release never shows old styles (v0.3.1, ADR-018 follow-up)
- [x] Installer stall after "Obtaining file:///…": build isolation removed + `install.log` (v0.3.1) — Adam: works
- [x] Each dub of a video is its own library entry; watch page links the other dubs (v0.4.1, ADR-022)
- [x] The program updates itself from `main` at start and with a button on the site (v0.5.0, ADR-024)
- [x] Full QA pass (3 agents): updater safe to fail, UI/copy fixes (v0.5.1)

### M8 — Session 5 (Adam, 2026-10-18)
- [x] One-click Windows start: `Start Dubber.cmd`, desktop shortcut with the program's icon, `?` bug fixed (ADR-025)
- [x] Windows install tested in CI on real Windows (`windows-install.yml`)
- [x] Upload a video file from the website (ADR-026)
- [x] Several links at once; YouTube playlists (ADR-026)
- [x] Library: one card per video + search (ADR-027)
- [x] Disk space on the Settings page + clear cache (ADR-027)
- [x] "What's new" after an update (ADR-027)
- [x] 0.6.1: readable Russian in the window (Consolas) + shortcut after a self-update — awaiting Adam's confirmation
- [x] README: step-by-step user guides in Russian and Hebrew covering every function
- [ ] First run on a clean PC (winget Python + ffmpeg) — Adam

### M9 — Session 7 (Adam, 2026-10-28)
- [x] Windows install on clean Windows 11 PCs: C++ runtime, no-winget fallback, component self-check (v0.8.0, ADR-029)
- [x] On-screen subtitles on the watch page: two switches, dub language / original (v0.8.0, ADR-030)
- [ ] Adam: fresh install on a Windows 11 PC; watch a dub with both subtitle switches

### M10 — Future (Adam, 2026-10-28)
- [x] Phone version: fully usable on iPhone and Samsung (`kanban/phone-app.md`, ADR-033) — built in 0.10.0
- [ ] Adam: Cloudflare account + 2 GitHub secrets → the mailbox deploys; send me its address (`phone.MAILBOX_URL`)
- [ ] Adam: pair his Samsung (QR), dub with the PC on and off; an iPhone if one is at hand
- [x] NVIDIA PCs: no "cublas64_12.dll" failure, Whisper on the card (0.10.1, ADR-034)
- [ ] Adam: re-dub on the new NVIDIA PC; faster after the background download?
- [x] «Оригинал»: card check, no CPU crawl, install progress bar, voice-free background (0.10.2, ADR-035)
- [x] Adam: «Оригинал» 5-min dub on the RTX 5060 Ti — runs on the card (~50% load); quality work → M11
- [x] Dub videos from Facebook, Instagram, TikTok + «Вход на сайты» login file (v0.9.0, ADR-031, `kanban/more-video-sites.md`)
- [x] Public videos without a login: yt-dlp `curl-cffi` impersonation (v0.9.0, ADR-032)
- [ ] Adam: dub a real TikTok, Instagram Reel and Facebook video without a login; report what fails
- [ ] If Instagram often needs a login: in-program login window (Edge own profile + DevTools cookies) — ask Adam first

### M11 — «Оригинал» quality (Adam, 2026-10-29/30)
- [x] No swallowed words: speed floor, bigger groups on big cards (0.10.3, ADR-036)
- [x] Listen-back check, ≤1.25× pace, names in the dub language's letters (0.10.4, ADR-037)
- [x] Who speaks each line, one sample per speaker, two voices at once (0.11.0, ADR-038)
- [x] Soft line edges (0.11.0, ADR-040); every dub its own library entry with date + time (0.11.0, ADR-039)
- [ ] Adam: re-dub with 0.11.0 and listen (STATUS Next steps 0)
- [x] One library card per dub (ADR-041, `kanban/library-card-per-dub.md`)
- [x] Misheard foreign lines: second-opinion language check + Claude prompt v4 (ADR-042)
- [ ] One-word lines, crosstalk (`kanban/original-voice-quality.md`)
- [x] No American accent in the Russian «Оригинал» dub — measured, Adam chose (b): convert only accented lines (0.12.0, ADR-043)
- [ ] Adam: dub with 0.12.0 «Оригинал» and listen (accent, voice)

### M4 — Nice to have
- [x] Queue of several links / playlists (v0.6.0)
- [ ] Telegram bot front-end
- [ ] ElevenLabs dubbing backend (paid, keeps original voice)
- [ ] Offline TTS fallback (Silero)
- [x] Voice cloning ("original voice", OmniVoice) — opt-in, NVIDIA GPU only, installed from Settings (v0.7.0, ADR-028)
- [ ] Adam: install it on his own NVIDIA PC (father's has an RTX 3050 4 GB — too small), dub with «Оригинал», report

## Open questions
- ~~Repo public?~~ — yes (self-update works from GitHub, 2026-10-18).
- ~~The user's work field~~ — every topic, so tools like the glossary must be general-purpose (Adam, 2026-10-17).
- Claude key for translation: built (ADR-017); Adam decides whether to buy credit. Estimate at 2026-10 prices: ~$0.10 per 10 min of
  speech on Opus 5.5 ($4/$20 per M tokens), ~$0.05 on Sonnet 5.5, under $0.01 on Haiku 5.5. The key would stay on
  the PC (env var), with a monthly spend limit set in the Anthropic Console; no payment code in Dubber.
- ~~Should one video keep several dub languages in the library?~~ — yes, one entry per dub; since 0.11.0 every run is a new entry (ADR-039)
  it (Adam, 2026-10-18, ADR-022, v0.4.1).
- Hosting on Hugging Face Spaces: researched, not now — YouTube blocks its servers (ADR-023).
- Windows confirmed as the target OS (Adam, 2026-10-17).
