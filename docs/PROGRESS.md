# Progress log

Newest entries at the top. One entry per working session / milestone.

## 2026-10-16 — Session 1d: documentation handoff
- Added `docs/STATUS.md` (start-here page for future sessions), linked from `CLAUDE.md`; fixed stale Gradio/Haiku
  references in RESEARCH/PLAN/DECISIONS/kanban; ticked M3 items already done; new card `kanban/windows-install-test.md`.
- Explained to Adam how to install on his PC (branch `claude/bold-davinci-qfv627`, `scripts/install_windows.bat`).

## 2026-10-16 — Session 1c: professional website
- Adam: the father is a professional, not elderly → modern product look. Researched design guidance and dubbing
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
  quality (Google blocks this server; the father's home connection should be fine).

## 2026-10-16 — Session 1: research, skills, foundation
- Agreed scope with Adam: runs on father's PC, free-first, outputs = dubbed MP4 + RU subtitles + transcript.
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
