# Plan & roadmap

_Last updated: 2026-10-16_ — current state at a glance: `docs/STATUS.md`. Task cards: `kanban/`.

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
- [ ] Optional: PR `claude/bold-davinci-qfv627` → `main` (so "Download ZIP" works without picking a branch)

### M3 — Quality
- [x] Smarter timing: merge short segments into sentences before translating (`segments.merge_into_sentences`)
- [ ] Glossary of domain terms (his work field) passed to the translator
- [x] Voice choice (male/female) in the UI
- [ ] Voice speed in the UI
- [ ] Optional Demucs: keep background music, remove English voice
- [x] Translation prompt asks for "dub-length" Russian when using Claude (`translate.CLAUDE_SYSTEM_PROMPT`)

### M3.5 — Dub timing that follows the speaker (Adam's report, research in `docs/RESEARCH.md` "Dub timing")
- [x] Research + measurement of the current timing (RU ≈ 1.47× EN; every line at the 1.5× cap; speed jumps)
- [ ] Word timestamps → sentence/phrase units with speech-only bounds; split long sentences at pauses
- [ ] Steady per-video pace + smoothed per-line rate (narrow band)
- [ ] Speed via Edge TTS `rate` (two-pass), `atempo` only as a small last correction
- [ ] Use following pauses before speeding up; minimal push-back
- [ ] Optional: length-budgeted translation with Claude (syllable budget, retry)
- [ ] Timing report in `output/<id>/` + tests for the timing planner

### M4 — Nice to have
- [ ] Queue of several links / playlists
- [ ] Telegram bot front-end
- [ ] ElevenLabs dubbing backend (paid, keeps original voice)
- [ ] Offline TTS fallback (Silero)

## Open questions
- What is the father's work field? (for the glossary)
- Translation quality: stay on free Google (offline fallback is clumsy) or add a Claude key (~$0.05–0.20 per 10-min video)?
- Which OS does his PC run? (Windows assumed)
