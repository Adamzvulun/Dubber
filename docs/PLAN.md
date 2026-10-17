# Plan & roadmap

_Last updated: 2026-10-17 (session 2)_ — current state at a glance: `docs/STATUS.md`. Task cards: `kanban/`.

## Goal
A Russian-speaking professional (not a developer) pastes a YouTube link into a local web page and gets:
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
- [ ] real run with Google translation (needs a non-datacenter connection — first run on father's PC)

### M2 — Russian web UI + installers
- [x] ~~Gradio app in Russian~~ (first version; replaced by the custom website in M2.5)
- [x] Windows `install_windows.bat` / `start_windows.bat` (+ desktop shortcut); Linux/macOS `install.sh` / `start.sh`
- [ ] Test the Windows installer on a real Windows PC
- [x] `docs/README.ru.md` user guide for the father
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
- [ ] Glossary passed to the translator — general-purpose (the father watches videos on every topic, Adam
  2026-10-17): the user adds his own terms; no field-specific list
- [x] Voice choice (male/female) in the UI
- [ ] Voice speed in the UI
- [ ] Optional Demucs: keep background music, remove English voice
- [x] Translation prompt asks for "dub-length" Russian when using Claude (`translate.CLAUDE_SYSTEM_PROMPT`)

### M3.5 — Dub timing that follows the speaker (Adam's report, research in `docs/RESEARCH.md` "Dub timing")
- [x] Research + measurement of the current timing (RU ≈ 1.47× EN; every line at the 1.5× cap; speed jumps)
- [x] Word timestamps → sentence/phrase units with speech-only bounds; split long sentences at pauses
- [x] Steady per-video pace + smoothed per-line rate (narrow band)
- [x] Speed via Edge TTS `rate` (two-pass), `atempo` only as a small last correction
- [x] Use following pauses before speeding up; minimal push-back
- [ ] Optional (paid, not now): length-budgeted translation with Claude (syllable budget, retry)
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
  (`kanban/translation-timing-regression.md`)

### M4 — Nice to have
- [ ] Queue of several links / playlists
- [ ] Telegram bot front-end
- [ ] ElevenLabs dubbing backend (paid, keeps original voice)
- [ ] Offline TTS fallback (Silero)

## Open questions
- ~~Father's work field~~ — every topic, so tools like the glossary must be general-purpose (Adam, 2026-10-17).
- Claude key for translation: Adam is still deciding (cost + safety). Estimate at 2026-10 prices: ~$0.10 per 10 min of
  speech on Opus 5.5 ($4/$20 per M tokens), ~$0.05 on Sonnet 5.5, under $0.01 on Haiku 5.5. The key would stay on
  the PC (env var), with a monthly spend limit set in the Anthropic Console; no payment code in Dubber.
- Should one video keep several dub languages in the library (today a new language replaces the old dub)?
- Windows confirmed for Adam's PC and the father's PC (Adam, 2026-10-17).
