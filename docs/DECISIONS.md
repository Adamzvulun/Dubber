# Decisions (ADR log)

Newest at the bottom. Format: context → decision → consequences.

## ADR-001 — Run locally on the user's PC (2026-10-16)
- **Context:** YouTube blocks many datacenter IPs; hosting costs money; the user is one person.
- **Decision:** Local app, opened in the browser on `127.0.0.1:7860` (first Gradio, now a custom FastAPI site — ADR-010), one-click Windows launchers.
- **Consequences:** No server to maintain. CPU-only speed must be acceptable → default Whisper `small` int8.

## ADR-002 — Free-first stack (2026-10-16)
- **Decision:** yt-dlp + faster-whisper + Google (deep-translator) / optional Claude + edge-tts + ffmpeg.
- **Consequences:** $0 by default. Translation quality improves if `ANTHROPIC_API_KEY` is set (cents per video).
  Paid voice cloning (ElevenLabs) is an optional future backend.

## ADR-003 — Outputs: dubbed MP4 + Russian SRT + transcript (2026-10-16)
- **Decision:** Every run produces `dubbed.mp4` (Russian audio, original ducked underneath, soft RU subs),
  `ru.srt`, `en.srt`, `transcript_ru.txt` (and bilingual `transcript_en_ru.txt` for learning).

## ADR-004 — Python package with one module per stage + per-video cache (2026-10-16)
- **Decision:** `dubber/<stage>.py`, each a pure function with file inputs/outputs; `pipeline.py` caches results in
  `work/<video-id>/` so a failed or repeated run resumes instead of starting over.
- **Consequences:** Stages are testable in isolation; swapping a backend (e.g. TTS) touches one file.

## ADR-005 — Third-party Claude skills are vendored after review (2026-10-16)
- **Decision:** Skills from GitHub are read in full before being copied into `.claude/skills/`, with their LICENSE and a
  pinned commit recorded in `docs/SKILLS.md`. Skills without a license are not copied (used as reference only).
  Scripts that install software or phone home without asking are stripped.

## ADR-006 — Claude translation uses `claude-opus-5-5` by default (2026-10-16)
- **Context:** Optional paid translator. A cheaper model was considered; the model choice is the user's call.
- **Decision:** Default `claude-opus-5-5` at effort `low`, structured JSON output (same line count guaranteed by
  schema + count check + retry in halves), server-side refusal fallback. Override with `DUBBER_CLAUDE_MODEL`.
- **Consequences:** ~$0.05–0.20 per 10-minute video. Only used when `ANTHROPIC_API_KEY` is set.

## ADR-007 — Web UI with Gradio, designed for an older non-technical Russian reader (2026-10-16) — superseded by ADR-010
- **Decision:** One column, 18px+ text, one big primary action, PT Sans / PT Serif (ParaType fonts made for Cyrillic),
  calm slate + blue palette, all text in Russian, errors that say what to do. Result video hidden until it exists.
- **Consequences:** No custom frontend to maintain; Gradio gives progress bar, player and downloads for free.

## ADR-008 — Offline translator as automatic fallback (2026-10-16)
- **Context:** Google's free endpoint is unofficial; it showed a robot check to our cloud test server and could do the
  same to a home user who translates a lot.
- **Decision:** `auto` = Google, switching for the rest of the run to an on-device model (Helsinki-NLP opus-mt-en-ru,
  Xenova ONNX export, Apache-2.0) on the first failure. Runs with onnxruntime + tokenizers (already pulled in by
  faster-whisper), so no PyTorch. `DUBBER_TRANSLATOR=offline` forces it.
- **Consequences:** Dubbing never stops because of Google; quality drops when the fallback is used.

## ADR-009 — yt-dlp needs deno; optional browser cookies (2026-10-16)
- **Decision:** Ship the `deno` PyPI package (a JS runtime yt-dlp requires for YouTube) and pass its path explicitly.
  Support `DUBBER_COOKIES=<cookies.txt>` for when YouTube demands "confirm you're not a bot".
- **Consequences:** Works without a system-wide deno install. Cookies are only needed on blocked networks
  (datacenters/VPNs); a spare Google account is recommended because YouTube may flag the account.

## ADR-010 — Custom website instead of Gradio (2026-10-16)
- **Context:** Adam wants a modern, professional site; his father is a professional, not an elderly beginner
  (ADR-007's assumption was wrong). Gradio limits layout and always looks like a demo.
- **Decision:** FastAPI server (`dubber/app.py`) with a small JSON API + a hand-built front-end (`dubber/web/`, plain
  HTML/CSS/JS, no build step). Pages: new video, library, watch page with a synced bilingual transcript.
  Design tokens and rules in `docs/DESIGN.md`. One background worker runs jobs one at a time.
- **Consequences:** Full design control, smaller install (Gradio removed), video seeking via HTTP range requests.

## ADR-011 — Optional dub without the original sound (2026-10-16)
- **Decision:** Switch "Оригинальный звук фоном" (on by default). Off → the default audio track is only the Russian
  voice; the English original stays available as the second audio track. `DUBBER_KEEP_BACKGROUND=0` for the CLI.
- **Consequences:** Music and effects disappear too when it is off (Demucs voice/music separation is a later option).

## ADR-012 — Plain HTTPS for Hugging Face model downloads (2026-10-16)
- **Context:** On Adam's Windows PC the first Whisper download failed inside huggingface_hub's Xet client
  ("CAS Client Error ... error sending request"), while plain HTTPS downloads are the long-proven path.
- **Decision:** `dubber/__init__.py` sets `HF_HUB_DISABLE_XET=1` unless the user set it; downloads retried 3×.
- **Consequences:** Possibly slower first download; one fewer native network stack to fail on home PCs/antivirus.

## ADR-013 — Dub timing: sentence lines, steady voice rate, no padding (2026-10-16)
- **Context:** Adam heard the dub rush and drag against the speaker. Measured: every chunk time-stretched near the 1.5×
  cap with jumps between chunks; Whisper chunks of 4–11 s cut mid-sentence; Edge clips padded with ~1.15 s silence.
- **Decision:** Lines = sentences from Whisper word timestamps (split at ≥1.2 s pauses / >10 s at the best break).
  Speak each line once to measure, plan a steady per-video rate (median RU/EN ratio, ±12% per line, ≤0.08 change
  between neighbours, faster only to fit before the next line, cap `DUBBER_MAX_SPEEDUP`=1.6), re-speak with Edge
  `rate`. Trim clip silence; atempo only ≤1.1× as a last correction. `timing.json` per video records the result.
  Paid length-budgeted translation (Claude) deferred — Adam asked for free improvements only.
- **Consequences:** TTS runs twice (≈2× Edge requests; still fast). Caches renamed (`_v2`/`_v3`), so existing videos
  are re-transcribed with word timings when dubbed again. Short translations may end a little early (pace kept steady
  instead of slowing down a lot).

## ADR-014 — Any source language, 12 dub languages, RU/EN interface (2026-10-16)
- **Context:** Adam's test video mixed English and French; he asked to dub any language, into other languages too.
  Measured: Whisper with `language="en"` **dropped the French passage**; auto-detect (`multilingual=True` too) picks one
  language per 30-s window and **dropped the English before it**.
- **Decision:** detect the language per stretch of speech (Silero VAD regions grouped into ≤20 s pieces; uncertain
  pieces re-checked region by region), transcribe each run of one language separately (single-language videos: one
  pass, as before). Google translates with `source="auto"` and re-sends lines left unchanged in mixed chunks.
  Curated targets in `dubber/languages.py` (ru default, en, he, uk, es, fr, de, it, pt, ar, zh, ja; male + female Edge
  voice each, verified against the live voice list). Offline translator stays as fallback for en→ru only. Output files
  are language-coded and listed in `meta.json` (`files`, `target_lang`, `source_lang(s)`); old videos read via legacy
  defaults. Website: dub-language select, RU/EN interface (`dubber/web/i18n.js`), RTL transcript lines.
- **Consequences:** translating into non-Russian languages needs Google (or a Claude key); mixed-language originals are
  tagged `mul` and labelled ORIG in the study transcript; the original transcript cache keeps its `segments_en_v2.json`
  name so existing videos aren't re-transcribed.

## ADR-015 — Cancel = stop at the next progress report, keep the cache (2026-10-16)
- **Decision:** `POST /api/jobs/{id}/cancel`. Queued jobs never start; a running job raises from its progress callback
  (called at every stage start and continuously in download, Whisper and TTS). No confirmation dialog: everything done
  so far stays in `work/<id>/`, so "Start again" resumes.
- **Consequences:** a stage without progress calls (model loading, final mux) finishes before the job stops — seconds.

## ADR-016 — Reliable translation for every dub language (2026-10-17)
- **Context:** Adam: French lines of a mixed video "not translated half the time, the other half gibberish". Causes:
  random Google refusals switched the rest of the video to the English→Russian-only offline model; mixed-language
  batches; stale forced-English transcripts.
- **Decision:** every line carries its spoken language (Whisper `base` detects it per speech region); translation in
  one-language batches; Google via its JSON endpoint with 2-4-8-16-30 s retries; fallback = NLLB-200 distilled 1.3B
  (CTranslate2 int8, any pair, CC-BY-NC — fine for this personal tool); quality gate before voicing; lines already in
  the dub language kept; deep-translator dropped. Caches versioned/content-keyed so old videos are redone.
- **Consequences:** first offline fallback downloads 1.4 GB; the watch page says when the offline backup translated.
  NLLB is good but not Google-grade (see RESEARCH "Every dub language"); a Claude key remains the quality option.

## ADR-017 — Claude translation from the website: key in settings, whole-video context, fallback chain (2026-10-17)
- **Context:** Adam wants the paid Claude option usable by his father (Windows, not a developer), with a general
  glossary (any topic). He also reported worse translation and timing after ADR-016; dub-length lines address timing
  directly. The old Claude path was CLI/env-only, not installed by the Windows installer, failed the whole dub on a
  bad key, got one-language batches without timing, and shared the free engines' cache.
- **Decision:**
  - The key is entered on a **Settings** page, checked with a free `models.list` call, saved to the git-ignored `.env`
    (`config.save_env`), applied immediately, and never sent back (only `…last4`). Model, Claude on/off
    (`DUBBER_TRANSLATOR` auto/google) and the glossary (`glossary.txt`) are set there too. Default model Opus 5.5
    (Adam's choice); Sonnet 5.5 and Haiku 5.5 offered with prices.
  - Requests that change state are refused when their `Origin` is another website (the server is local, but a page
    open in the same browser could otherwise post to it).
  - Claude gets the **whole video** (≤200 lines per request with earlier lines as context): each line's language,
    time slot (`timing.slots`) and a character budget (slot × the dub language's chars/second × 1.15, estimates in
    `languages.chars_per_second`); prompt asks for spoken, dub-length lines; structured JSON output; streaming;
    effort `low`; server-side refusal fallback (not on Haiku).
  - Errors map to `TranslatorUnavailable(code)` (auth / permission / credit / unavailable / refusal) and the
    `Translator` moves down an ordered chain **Claude → Google → NLLB**, recording why; the watch page says so.
  - Cost = usage × price table, stored in `meta.json` and shown on the watch page. Claude translations have their own
    cache keyed by model + glossary; a run that fell back is cached as free, so Claude is retried next time.
  - `anthropic` becomes a regular dependency (installer installs it).
- **Rejected:** storing the key in the browser (would travel with every request and live in browser storage); a
  Windows credential vault (extra dependency for a single-user PC where `.env` is already the settings file);
  validating with a real translation call (costs money; credit problems surface at dub time with a clear note).
- **Consequences:** no real Claude translation could be run in the sandbox (no key); the request shape is unit-tested
  and the real SDK accepted it (401 with a dummy key mapped to "auth"). Adam's first run with a key is the end-to-end
  check. The chars/second table is an estimate to calibrate from real dubs.

## ADR-018 — Updates always visible (no-cache site, version, single instance) and a learned time-left estimate (2026-10-17)
- **Context:** after updating to `main`, Adam saw no Settings icon although `main` has it. Two ways our code showed
  an old page: a still-running old server keeps port 7860 (the new one fails, but the browser was opened anyway and
  showed the old server), and the site's own files were served without `Cache-Control`, so a browser may reuse old
  copies. Nothing showed which version runs. Adam also asked for a "time left" next to the elapsed timer.
- **Decision:**
  - Site files are served with `Cache-Control: no-cache` (revalidated by ETag, 304 when unchanged).
  - `__version__` (0.3.0) in the page footer, `GET /api/version`, and the start message. On start, if the port
    already answers, print "already running (version X / old version)", don't open the browser, exit 1. The browser
    opens only once *this* server answers with *its* version.
  - Time left (`dubber/eta.py`): per-stage timings of the running job; stage shares = defaults blended (as 2 jobs)
    with the last 10 finished jobs ≥ 60 s on this PC (`work/stage_times.json`); left = work seconds / share done ×
    share left; stages finished in < 2 s (cache) are ignored; no estimate before 15 s / 3 % of work. Shown in whole
    minutes (< 2 min → "under 2 min"), changing at most every 10 s.
- **Rejected:** front-end-only ETA from the overall progress bar (fixed weights; cached stages make it jump);
  per-stage speed models from video duration (needs the duration plumbed out of the pipeline; the learned shares get
  most of the benefit with far less code).
- **Consequences:** the first dubs on a new PC use the default shares; the estimate improves after a few dubs. Every
  release must bump `__version__` (and `pyproject.toml`).
