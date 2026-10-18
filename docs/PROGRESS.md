# Progress log

Newest entries at the top. One entry per working session / milestone.

## 2026-10-18 — Session 5b: question marks in the window (v0.6.1)
- Adam merged PR #9; after a restart the PC updated itself to 0.6.0. The shortcut appears once «Start Dubber» runs
  (the self-update restarts only the program, not the launcher). His screenshot of the launcher window: title
  «Дубляж видео» correct, every Russian line `?` — also Python's own output, so not an encoding problem but the
  console font (Raster Fonts have only the system language's letters). Fix: switch to Consolas at start (ADR-025
  follow-up). Not verifiable here or in CI (no visible console) — Adam checks.

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
