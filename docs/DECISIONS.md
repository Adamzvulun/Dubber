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

## ADR-007 — Web UI with Gradio, designed for a non-technical Russian reader (2026-10-16) — superseded by ADR-010
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
- **Context:** Adam wants a modern, professional site; the user is a professional, not a beginner
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
- **Context:** Adam wants the paid Claude option usable by a non-developer on Windows, with a general
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
- **Follow-up (v0.3.1, same day):** no-cache could not reach copies saved *before* it existed: on a refresh,
  Chromium browsers re-check only the page and reuse fresh-by-heuristics `styles.css`/`app.js` — Adam saw the new
  page with the old styles (huge gear, raw `nav.settings`). The page is now served by the app with its files under
  versioned addresses (`?v=<version>.<newest file time>`, `app.asset_tag`), so a release can never reuse old copies.
  Reproduced (old `main` with 10-day-old files → new server → refresh) and verified fixed; a simulated next release
  shows on the first open without a refresh. Updating from ≤ 0.3.0 may need clearing the browser's cached files once
  (Adam: Ctrl+F5 did not help in Opera GX).
- **Consequences:** the first dubs on a new PC use the default shares; the estimate improves after a few dubs. Every
  release must bump `__version__` (and `pyproject.toml`).

## ADR-019 — Hebrew voice: keep Edge with plain text; fix spelling in the translation (2026-10-18)
- **Context:** Adam: the Hebrew dub mispronounces "almost every second word" — wrong stress and syllables, e.g. "the
  rest" read "iter" instead of "yeter". Free tools only.
- **Measured** (`tools/qa_hebrew_voice.py`, RESEARCH "Session 3"): 50 benchmark sentences with gold IPA + stress,
  scored by a Hebrew-IPA Whisper. Word errors incl. stress: Edge Avri plain **0.231**, Phonikud Piper voice 0.233,
  Edge Hila 0.256, Edge + niqqud on ambiguous words 0.251, Edge + full niqqud (Phonikud) 0.313.
  Edge says יתר correctly in every context; it says the spelling **ייתר** "yiter" — the dub read a misspelling.
- **Decision:** keep Edge with plain text (male voice is the default and scores best). Claude gets a spelling note
  per dub language (`translate.SPEECH_NOTES`): Hebrew — standard ktiv male, no extra yod/vav, with the ייתר example;
  Russian — write "ё". Part of the Claude prompt version (ADR-021), so cached Claude translations are redone.
- **Rejected:** niqqud before Edge (Edge misreads vowelled text — worse in both variants); Phonikud's offline voice
  (ties on accuracy, less natural, non-commercial licence, one more 60 MB model); paid voices (Adam: free only).
- **Consequences:** the free Google/offline path gets no spelling rule (can't be prompted). Homographs and
  grammatical gender (לך) stay a limit of any text-to-speech from plain text.

## ADR-020 — Remove the speaker's voice, keep music and sounds (Demucs v4, ONNX on CPU) (2026-10-18)
- **Context:** the original soundtrack plays quietly (15 %) under the dub, voice included, or not at all. Adam liked
  the Demucs idea; off by default, a switch.
- **Decision:** `dubber/separate.py` runs Demucs v4 `htdemucs` as ONNX (`StemSplitio/htdemucs-onnx`, fp16 weights,
  166 MB, MIT, downloaded on first use from Hugging Face) with onnxruntime — already a dependency; background = drums
  + bass + other. 7.8-s windows, quarter overlap with complementary cross-fades; audio read from and written to
  memory-mapped files (an hour-long video never sits in memory). Cached as `work/<id>/background_htdemucs.wav` (any
  dub language reuses it). A new stage "Убираю оригинальный голос" (`pipeline.stages()`, job card shows it only when
  on; eta learns it only from jobs that ran it). Mix: background at 0.7, ducked by `sidechaincompress` while the dub
  speaks; track 2 stays the untouched original. Website: switch «Убрать голос диктора» under the background switch
  (disabled when the background is off); API/CLI/env: `remove_voice` / `--remove-voice` / `DUBBER_REMOVE_VOICE`.
- **Rejected:** the `demucs` PyTorch package (≈ 200 MB+ torch on Windows, torchaudio saving breakage, weights host
  blocked here); MDX-Net models via audio-separator (more dependencies); a three-way background menu (two switches
  are simpler and the old `background` setting keeps its meaning).
- **Consequences:** ≈ +5 min per 10 min of video on 4 CPU cores (measured idle; card claims 0.2× real time on a fast
  CPU). The ONNX export is a community one: checked here by ear-free tests (no words left, music level unchanged).

## ADR-021 — Transcription fixes and a better Claude request (2026-10-18)
- **Context:** Adam: translations "still off sometimes, even with Opus". Measured on real recorded speech (FLEURS).
- **Decision:**
  - Language per region is chosen among the languages of the whole video (`transcribe.video_languages`: ≥ 15 % of
    the speech or one sure ≥ 2 s region) — stray guesses (Hebrew regions called Italian/French) made gibberish.
  - Language runs keep up to 1 s around them, never past the middle of the pause (0.2 s lost first words).
  - Whisper `small` stays the default: `large-v3-turbo` is better on French/Hebrew but skipped an English sentence
    twice, hallucinated short lines and is ~1.5× slower.
  - Claude: the video's title/channel as topic; "text comes from speech recognition — translate what was most likely
    said"; a line may be part of a sentence; meaning before the character budget; effort `low` → `medium`; spelling
    notes (ADR-019). `CLAUDE_PROMPT_VERSION` is part of the Claude cache key.
- **Consequences:** mixed EN+FR word errors 0.199 → 0.153 (English part 0.272 → 0.171); Hebrew regions all Hebrew.
  The Claude changes are unit-tested only — no key in the sandbox; Adam's next dub with a key is the real check.
  Cached Claude translations are redone once (cost of one translation per video).

## ADR-022 — One library entry per dub, not per video (2026-10-18)
- **Context:** Adam dubbed one video twice (another language and voice): both cards opened the newest dub, because
  every dub of a video was written into the same `output/<video-id>/` folder.
- **Decision:** each dub gets its own folder `output/<video-id>--<lang>-<hash6>/` (`pipeline.dub_id`; the hash covers
  language, voice, background and voice-removal). Redoing a dub with the **same** choices replaces it (Adam's choice:
  no duplicates, e.g. after adding a Claude key). `meta.json` keeps `id` (= folder) and `video_id`; the watch page
  lists the video's other dubs (`siblings` in `/api/videos/<id>`); library cards show language · voice. The
  `work/<video-id>/` cache is shared, so another language reuses download and transcription. Folders from before
  0.4.1 keep working as they are (`video_id` defaults to the folder name); no migration.
- **Rejected:** one card per video with a language picker inside (more UI, and deleting one dub gets fiddly); a new
  entry on every run (duplicates to clean up by hand).

## ADR-023 — Hosting on Hugging Face Spaces: researched, not adopted for now (2026-10-18)
- **Context:** Adam asked whether Hugging Face Spaces could host Dubber (no install on the user's PC, open from
  anywhere). Details and sources: `RESEARCH.md` → "Hosting on Hugging Face Spaces".
- **Decision:** stay on the home PC for now. The app itself would run on a Docker Space unchanged, but: YouTube
  blocks Hugging Face's datacenter addresses (the main input fails — the same block we hit in the cloud sandbox),
  a Docker Space needs HF PRO ($9/month), the free 2 vCPU is slower than the PC, the disk is wiped on restart (a
  paid Storage Bucket is needed for the library), and a public URL would let anyone spend the Claude key (needs a
  private Space + HF login, or our own login page).
- **Revisit when:** the website can take an uploaded video file (then YouTube isn't needed on the server), or a
  reliable YouTube path from a server exists. A "Duplicate this Space" demo for others is possible then too.

## ADR-024 — The program updates itself from `main` (2026-10-18)
- **Context:** Adam was tired of downloading the newest ZIP by hand after every merge (the real reason he looked at
  hosting, ADR-023). He chose to make the repository public and to update both automatically and with a button.
- **Decision:** `dubber/update.py`. At start, `app.main()` reads `__version__` from `main`
  (raw.githubusercontent.com); if it is higher, it downloads `main` as a ZIP (codeload.github.com), checks it is a
  Dubber, replaces the program files one by one (`.partial` + rename) and starts the new version. The site asks at
  most once an hour and shows «Вышла новая версия — Обновить»; the button installs, the server restarts itself and the
  page reloads on the new version. Rules: the user's data (`.env`, `glossary.txt`, `work/`, `output/`, `models/`,
  `.venv/`, `install.log`) is never written; files dropped from `main` are removed (`.dubber-files` lists what the
  last update installed); `pip install -e .` only when `pyproject.toml` changed; yt-dlp refreshed every update; no
  internet / GitHub down → the current version starts as usual; refused while a dub runs; off in a git checkout and
  with `DUBBER_AUTO_UPDATE=0`. `start_windows.bat` keeps the start and `pause` on one line (cmd reads a running .bat
  line by line). Rehearsal without GitHub: `DUBBER_UPDATE_SOURCE`.
- **Rejected:** `git pull` (needs Git installed on the PCs and a clone instead of the ZIP folder); a private repo with
  a read-only token on each PC (expires, one more secret); a Windows scheduled task (updates files while the program
  runs).
- **Consequences:** a merge into `main` reaches the PCs on their next start, so `main` must stay releasable and every
  release must bump the version. Each in-session update leaves the old process waiting for the new one (a few MB).

