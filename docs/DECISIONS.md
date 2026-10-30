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
- **Follow-up (v0.5.1, QA):** `dubber/__init__.py` is written last, after `pip`; a `.dubber-deps` stamp (sha1 of
  the installed `pyproject.toml`, "pending" while installing) reruns pip until it succeeded — so any failed update
  leaves the old version and is retried on the next start.

## ADR-025 — One-click Windows start: "Start Dubber.cmd" + a PowerShell script, Unicode shortcut (2026-10-18)
- **Context:** Adam: the installer still printed question marks and never created the shortcut; the user should
  click one icon that installs what's missing, creates a desktop shortcut with the program's own icon, and starts.
- **Cause (reproduced on Windows in CI):** Russian text inside `.bat` files depends on the console code page, and
  `WScript.Shell` saves shortcuts in the PC's ANSI code page — on non-Russian Windows the name «Дубляж видео» became
  `?????? ?????` and saving failed (the same message Adam saw).
- **Decision:** `Start Dubber.cmd` (ASCII only, one line) runs `scripts/windows/dubber.ps1` (UTF-8 with BOM, so
  Windows PowerShell 5.1 reads the Russian text). Every run: Python/ffmpeg via winget if missing, with PATH re-read so
  it continues in the same window; components once (`.venv/dubber-installed`; an existing working install is
  recognised); yt-dlp refreshed every 3 days; desktop + Start menu shortcut written through `IShellLinkW` (Unicode)
  with `dubber/assets/dubber.ico` (the site's logo, `tools/make_icon.py`); then the program. The old `.bat` files call
  the same script; files from the ZIP are unblocked. ASCII file name on purpose: Windows' ZIP extractor can garble
  non-ASCII names. CI job `windows-install.yml` installs, reads the shortcut back and starts via the `.cmd`.
- **Rejected:** fixing the `.bat` (code pages differ per PC); a compiled installer (.exe/MSI — signing, build step).
- **Follow-up (0.6.1, Adam's screenshot):** the window title was right but every Russian line — Python's too — showed
  `?`: the console used "Raster Fonts", which only has the system language's letters. The script now switches a raster
  font to Consolas (`SetCurrentConsoleFontEx`) before printing; a TrueType font the user chose is kept. CI can't render
  a console, so it only checks the helper compiles and runs in PowerShell 5.1.

## ADR-026 — Upload a file; several links and playlists (2026-10-18)
- **Decision:** `POST /api/upload?name=` streams the raw body (no new dependency — FastAPI forms need
  python-multipart) to `work/uploads/<sha1-12>/<name>` with a fixed mtime, so the same file again gets the same
  `local_video_id` and reuses the cache; a job gets `{file}` (validated token, never a raw path); the upload is
  removed after a finished dub. The link field is a textarea: one job per link. Playlists via yt-dlp flat extraction
  (`download.playlist_entries`, max 200): a playlist page queues all; a video inside a playlist asks every time
  (Adam's choice); YouTube mixes (`list=RD…`) count as single videos.

## ADR-027 — Disk space, "What's new", grouped library (2026-10-18)
- **Decision:** `/api/storage` sizes `work/` per video, uploads, `output/`, the HF model cache; clearing a video's
  or all cache is refused while a dub is queued/running (the library doesn't use `work/`). `dubber/changelog.json`
  holds each release's user-facing changes (RU+EN, a test requires the current version); the page shows them once
  after an update (localStorage `dubber.seenVersion`, nothing on a first visit). The library groups dubs per
  `video_id` client-side (tag per language; the card opens the newest dub) with a search box.

## ADR-028 — Voice cloning with OmniVoice (from VoiceStudio): only with an NVIDIA GPU; Edge stays the default (2026-10-19)
- **Context:** Adam asked whether VoiceStudio (open-source ElevenLabs-like app) can improve the dubbing. Its value for
  us is the OmniVoice model: the dub in the original speaker's own voice, and lines spoken to an exact length.
  Research and measurements: `docs/RESEARCH.md` → "VoiceStudio / OmniVoice".
- **Proposal:** don't adopt the VoiceStudio app (Electron + AGPL, a second program to install and run). If Adam's PC
  has an NVIDIA GPU (≥ 6 GB), add OmniVoice as an **optional** voice ("Голос оригинала"): `pip install omnivoice`,
  reference cut from the voice-free track (`separate.py`), `duration=` from the line's slot, for languages with
  enough training data (not Hebrew). Edge stays the default and the fallback. Without a GPU: no — measured ≈ 20×
  slower than real time on 4 CPU cores (≈ 2 h per 10-min video).
- **Decision (Adam, 2026-10-19):** his father's PC has an RTX 3070 (8 GB) + i7-11700 → build it as an opt-in voice
  «Оригинал» (`dubber/clone.py`, v0.7.0). His choices: **each line copies whoever said it** (reference = the same
  moment of the Demucs vocals stem, short lines joined with neighbours across pauses ≤ 1 s up to 3–15 s); **Hebrew →
  Edge** (male voice, note on the watch page); **installed from the Settings page** (nvidia-smi check ≥ 6 GB, then
  `pip install torch torchaudio --index-url …/cu128`, `omnivoice==0.2.1`, a CUDA check + model download in a separate
  Python; marker `.venv/dubber-omnivoice`). Lengths: the model's own estimate per line → `timing.plan_rates` (same
  steady-pace rules as Edge) → `duration=` per line; 4 lines per model call (one by one after a failure); clips
  levelled to RMS 0.1. With the original voice the voice is split off **before** TTS (stage order changes on the job
  card and in the time-left estimate). Any failure → Edge male voice + `voice_notes` in meta.json, never a failed dub.
- **Not verified here:** speed and quality on a real NVIDIA card (no GPU in the sandbox; estimate 0.2–0.4× real time
  on the 3070 from the authors' H100 numbers). The CUDA install path is the first thing to check on Adam's PC.

## ADR-029 — Windows install: supported Python 3.10–3.14 only, C++ runtime, no-winget fallback, self-repair (2026-10-28)
- **Context:** Adam: "some package was missing" installing a few days ago. The Windows CI reproduced it: pip "No
  matching distribution found for onnxruntime>=1.17 (from versions: none)". **Cause:** Python 3.15 came out in
  October 2026; the launcher took any Python ≥ 3.10 and `py -3` picks the newest, and onnxruntime has no 3.15 build
  yet (same message with `pip --platform win_amd64 --python-version 3.15`; a plain venv on 3.12 on the same runner
  downloads it fine). The audit also found: onnxruntime and ctranslate2 import `MSVCP140.dll`/`MSVCP140_1.dll`
  (Python doesn't ship them; the CI image has them, so CI couldn't notice); a fresh Windows 11 may have no winget yet.
- **Decision:** `dubber.ps1` uses only 64-bit Python **3.10–3.14** (`$PythonMax`; `py -3.12` first), installs 3.12
  when none fits, and rebuilds a `.venv` made from an unsupported or missing Python. Raise `$PythonMax` (and
  `scripts/install.sh`) only after checking every component has a win_amd64 wheel for the new version. The Microsoft
  Visual C++ runtime (≥ 14.40) is checked every start and installed (winget, else `aka.ms/vs/17/release/vc_redist`,
  UAC prompt). Without winget Python (python.org 3.12.10, per user) and ffmpeg (gyan.dev, else BtbN, into
  `ffmpeg/` in the program folder — `config.use_local_ffmpeg` puts it on PATH; kept by the updater) are downloaded.
  Every start runs `python -m dubber.deps` (exit 1: components missing → `pip install -e .`; exit 2: a native module
  doesn't load → C++ runtime). A first install in a folder deeper than 90 characters without long paths enabled
  stops with a plain message. CI: new `clean-pc` job (`DUBBER_SETUP_TEST=1`: no winget, everything downloaded, folder
  and model cache with Russian names, a too-new venv rebuilt, a removed component repaired).

## ADR-030 — On-screen subtitles: two switches, one browser-drawn text track (2026-10-28)
- **Context:** Adam asked for real-time subtitles on the dubbed video. The video had hidden `<track>` files only
  reachable through the player's small CC menu, one language at a time.
- **Decision (Adam's choice):** two switches under the player — the **dub language** and **«Оригинал»** — any of
  one, both or none (dub on by default, choice in localStorage `dubber.ccDub` / `dubber.ccSrc`). Built as **one
  `addTextTrack` track with `VTTCue`s** made from `segments.json`, not an HTML overlay: the browser draws it, so it
  shows in full screen and in iOS's native player (future phone version). The dub line follows the **dub voice**
  (`/api/videos/{id}` → `spoken` from `timing.json`: start + delay … + spoken), the original follows the speaker;
  each line shown ≥ 1.2 s and held over gaps < 0.8 s. With both on, the timeline is cut at every line edge and each
  piece gets **one** cue (dub line on top, original under it in yellow `::cue(.src)`) — two overlapping cues are
  stacked in an order that depends on line wrapping. Each line is wrapped in a bidi first-strong isolate (an English
  line under Hebrew would otherwise be laid out right to left). The player's own CC menu stays in sync with the
  switches. The `<track>` files are no longer attached (they'd duplicate in the CC menu); the `.srt`/`.vtt` files
  and the MP4's soft subtitles are unchanged.

## ADR-031 — TikTok, Instagram, Facebook: yt-dlp + a login file from the Settings page (2026-10-28)
- **Context:** Adam asked to dub videos from Facebook, Instagram and TikTok. yt-dlp already extracts all three, but
  Instagram (and many Facebook and some TikTok posts) need a logged-in session, TikTok often serves HEVC, and other
  sites' ids can collide or contain characters unfit for a folder name. Adam and his father use Chrome and Edge on
  Windows, whose cookies other programs can't read (app-bound encryption), so yt-dlp's `cookiesfrombrowser` is out.
- **Decision (Adam's choice: a cookies file in Settings):** Settings → «Вход на сайты» with a step-by-step guide for
  the open-source "Get cookies.txt LOCALLY" extension (Chrome Web Store; Edge after "allow other stores") and an
  upload button. `dubber/sites.py` keeps **only** cookies of YouTube/TikTok/Instagram/Facebook (Netscape or the JSON
  some extensions export), **merges per site** (a new Instagram file replaces only the Instagram login, so files for
  several sites add up), and reports per site whether a login cookie (`sessionid`, `c_user`, `LOGIN_INFO`...) is
  there and until when. Saved as `cookies.txt` in the program folder (git-ignored, kept by the updater, 0600 on
  POSIX); `download.base_opts` passes it to yt-dlp (DUBBER_COOKIES still overrides). API `GET/POST/DELETE
  /api/cookies` (Origin check like the other changing calls). Login, private and unsupported-site errors get their
  own messages pointing to the panel.
- **Downloads:** H.264 is preferred also among combined formats (`b[vcodec^=avc1]`); anything else (HEVC from TikTok,
  an iPhone upload) is re-encoded to H.264/AAC ≤ `max_height` (`media.to_h264`), so the dub plays in every browser
  (the mux copies the video). Work folders: `sites.video_id` — YouTube ids unchanged (old caches), others
  `<site>-<id>` or `<site>-<sha1>`; the channel falls back to the uploader's name.
- **Not verified here:** real TikTok/Instagram/Facebook downloads — the sandbox can't reach these sites (network
  policy; they also block datacenter IPs). Covered by tests with a yt-dlp stand-in; Adam tests real links.

## ADR-032 — No login for public TikTok/Instagram/Facebook videos: yt-dlp with curl-cffi (2026-10-28)
- **Context:** Adam: installing an extension and uploading a cookies file (ADR-031) is too much for the user — find a
  way without a login. Research: `docs/RESEARCH.md` → "TikTok, Instagram, Facebook without a login".
- **Decision:** depend on `yt-dlp[default,curl-cffi]`. With curl_cffi yt-dlp's requests look like a real browser's:
  TikTok stops answering with a bot-challenge page, and the Instagram extractor runs its logged-out GraphQL query
  (it is skipped without impersonation, which is why public reels failed). Public videos of all three sites then
  need no login. The launcher's 3-day refresh, the updater and `scripts/install.sh` upgrade `yt-dlp[default,curl-cffi]`
  (a plain `pip install -U yt-dlp` would not install the extra), and `dubber.deps` checks the extras' packages too,
  so PCs that installed before 0.9.0 get curl_cffi on their next start. The «Вход на сайты» panel stays as the
  fallback for private/followers-only posts and Instagram's anonymous rate limit (new message: wait an hour or add
  a login); its text now says that usually no login is needed and the guide is folded under "if a video won't
  download".
- **Rejected:** third-party download sites / public cobalt instances (privacy, terms, bot checks), self-hosted cobalt
  (Docker), reading Chrome/Edge cookies (app-bound encryption).
- **Next, if Adam finds Instagram still needs a login too often:** an in-program login window — Edge with its own
  profile folder + DevTools protocol to read the cookies (RESEARCH, option 5). Not built yet; ask Adam first.
- **Not verified live:** the sandbox can't reach the sites. Verified: curl_cffi installs (Windows wheels 3.10–3.14),
  yt-dlp lists curl_cffi impersonation targets (unit test + Windows CI step).

## ADR-033 — Dubber on the phone: the same website as an installable web app, the home PC through a Cloudflare quick tunnel, a mailbox for links while the PC is off (2026-10-28)
- **Context:** Adam: scroll TikTok/Instagram/Facebook/YouTube on the phone, copy a link, paste it into Dubber on
  the phone; Samsung for him and his father, iPhone must work too; from anywhere (home or mobile data); dub at once
  when the PC is on, else queue and dub when it starts (send-and-forget); a home-screen icon, not a store app; and
  **install as simple as possible: one click, the install does anything external, minimal taps** (this ruled out
  Tailscale, chosen first: an app and an account sign-in on every PC and phone).
- **Decision:**
  - **The phone never dubs** (Whisper, Demucs, voices need the PC). Each phone pairs with its own household's PC.
  - **Reaching the PC:** `cloudflared tunnel --url http://127.0.0.1:7860` (a free Cloudflare *quick tunnel*: no
    account) started with the program (`dubber/phone.py`); cloudflared is downloaded into `cloudflared/` on the first
    start (GitHub releases, `latest`), kept by updates. The server still listens on 127.0.0.1 only. Requests that
    come through the tunnel (Cf-Ray) must carry the household token (`X-Dubber-Token`, or `?t=` for video/picture/
    download addresses) and may only dub, list jobs/videos, play/download/delete videos and upload (`PHONE_ROUTES`);
    settings, logins, updates, disk space and the original-voice install stay PC-only. CORS only for the phone app.
  - **The mailbox:** a Cloudflare Worker (`cloud/worker/`, free plan, KV) on Adam's account serves the phone app at
    `https://dubber.<name>.workers.dev/p/<token>/` and keeps per household (key = SHA-256 of the token) the PC's
    current tunnel address and the links left while the PC was off (30 days). The PC announces its address at start
    and every 5 min and pulls links every minute (`PhoneBridge`). Deployed by `.github/workflows/deploy-phone.yml` on
    every merge to `main` (secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`), so phones and PCs stay on one
    version. `phone.MAILBOX_URL` holds its address.
  - **The phone app = the same `dubber/web/`** (relative file addresses; `app.js` switches to phone mode under
    `/p/<token>/`): `manifest.webmanifest` (standalone, icons, Android share target → Share → «Дубляж»),
    `sw.js` (opens without the PC), «Вставить» (clipboard), «Установить на телефон» (Android install prompt), an
    iPhone hint (Share → Add to Home Screen), PC on/off bar, «Ждут компьютера» list. The token is in the path, not
    in browser storage, because an iPhone home-screen app does not share Safari's storage.
  - **Pairing:** Settings → «Телефон» shows a QR code (`segno`) of the household's phone-app address.
- **Rejected:** Tailscale (accounts + app everywhere), home Wi-Fi only (Adam wants anywhere), a rented server that
  dubs (cost; YouTube blocks datacenters, ADR-023), store apps (fees, review, a Mac for iPhone), queue on the phone
  only (a home-screen app can't send in the background).
- **Risks:** quick tunnels are offered "for testing", without an uptime guarantee; if they turn out flaky, the
  worker can create a named tunnel per household under Adam's account (needs a domain, ~$10/year) — users would see
  no difference. Uploads through Cloudflare are limited to 100 MB per file (message on the phone).
- **Verified here:** worker unit tests (Node), PC side unit tests (token, routes, CORS, bridge, tunnel log parsing,
  download), and an end-to-end run with a local stand-in for Cloudflare (`tools/phone_dev.mjs`: mailbox + tunnel)
  in Chromium with Samsung- and iPhone-sized phones: pairing, PC on → dub, library + video + download through the
  tunnel, PC off → queued → PC back → dubbed (in the chosen language), share target, paste, offline app, RU/EN,
  dark. **Not verified:** a real quick tunnel and the real Worker (sandbox: running downloaded binaries is blocked;
  the Windows CI job runs real cloudflared), real Samsung/iPhone.

## ADR-034 — Whisper on an NVIDIA card: never fail, fetch NVIDIA's libraries automatically (2026-10-29)
- **Context:** Adam's new PC (0.10.0): every dub failed with "Library cublas64_12.dll is not found or cannot be
  loaded". faster-whisper/ctranslate2 4.8 with `device="auto"` picks CUDA whenever an NVIDIA driver is present, but
  needs NVIDIA's cuBLAS 12 and cuDNN 9 DLLs, which neither Python nor the driver installs. Older test PCs had no card.
- **Decision (Adam: "fix + auto speed-up"):**
  - `transcribe.transcribe` runs on the requested device and, on an error naming cublas/cudnn/cudart/nvrtc/cuda,
    redoes the work on the CPU (int8) and remembers that for the rest of the run (`_gpu_failed`). A dub never fails
    for a missing or broken GPU library.
  - `dubber/gpu.py`: on Windows with an NVIDIA card (`clone.gpu_info`, nvidia-smi) and the packages missing, `main()`
    starts a background `pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12>=9,<10"` (~1 GB, once, log
    `work/gpu-install.log`); `use_dll_dirs()` (called from `config.py` at import and after the install) adds
    `site-packages/nvidia/{cublas,cudnn}/bin` to PATH and `os.add_dll_directory`. `DUBBER_DEVICE=cpu` opts out.
  - Any GPU-library error that still reaches the job card gets a clear RU/EN message.
- **Rejected:** CPU only (slower on the PCs that have a card); asking the user to install CUDA (clicks, 3 GB).
- **Not verified:** a real NVIDIA card (none here or in CI). Windows CI checks the wheels resolve for the PCs' Python.

## ADR-035 — «Оригинал»: check the card for real, never crawl on the processor, voice-free background (2026-10-29)
- **Context:** Adam's new PC (RTX 5060 Ti 16 GB): a 5-minute «Оригинал» dub estimated 90 minutes and Task Manager
  showed the card idle (its "3D" graph does not show CUDA work, so idle there proves little). OmniVoice silently
  falls back to the processor when PyTorch doesn't see the card (~20× slower than real time = the 90 minutes), and
  nothing told the user. He also asked whether the two background switches should be on with «Оригинал».
- **Decision:**
  - `clone.cuda_status()`: a tiny computation on the card in a separate Python (catches "not available" and "no
    kernel image" for a card newer than the PyTorch build), once per run, in the background for the Settings page
    («Голос оригинала работает на видеокарте (CUDA x)» or why not + «Установить ещё раз»); reset after an install.
  - `pipeline.clone_choice`: when the check fails, the dub uses the Edge voice at once with the note
    `clone:no_gpu` (no separation step, no hours on the CPU). `DUBBER_CLONE_DEVICE` still forces a device.
  - The program's window prints where Whisper and OmniVoice run and the seconds per group of lines; the time-left
    estimate learns «Оригинал»'s voice step apart from Edge's (`tts_clone` in `eta.py`).
  - With «Оригинал» and the background on, the background is always the voice-free one (the voice is separated
    anyway, so it costs nothing; otherwise the same person is heard twice). The form shows the switch on and locked.
  - Install progress bar: bytes downloaded (pip's log + its temp file; the Hugging Face cache) against the known
    sizes, per step (`Installer.progress`); pip runs with `--no-cache-dir` (no second 3 GB copy).
- **Not verified:** a real NVIDIA card. Adam: Settings line, then a 5-minute «Оригинал» dub and the program window's
  lines «Распознаю речь: …» / «Голос оригинала: …».

## ADR-036 — «Оригинал»: a speed floor per line, bigger groups on big cards (2026-10-29)
- **Context:** Adam's first «Оригинал» dub on the RTX 5060 Ti (a 5-min film scene, 114 lines): the voice copy was
  good and ran on the card, but at ~50% load; sentences sounded "swallowed or warped". Its `timing.json`: whole lines
  spoken in 0.14–0.26 s with 2–5 s of room (OmniVoice's own estimate, without its short-line boost — ADR-028/RESEARCH
  — is far too short for short lines), and crowded stretches planned up to 1.6× (the planner's smoothing lifts the
  neighbours too). OmniVoice follows `duration=` closely, so it crammed the words. The same dub's `meta.json` said
  `"background": false` — the switch was off for that job, not a mixing bug.
- **Decision:**
  - `clone.min_seconds(text)` = 0.2 s + syllables / 7 per second (`clone.syllables`: Cyrillic vowels, Latin vowel
    runs, kana/Chinese characters, Arabic letters / 2). Every line asks for at least that; a line that then runs past
    its slot pushes the next one back (align.py, as with Edge). `timing.json` shows the rate really asked for.
  - Lines per model call from the card's memory (`clone.batch_for`: 12 at ≥ 14 GB, 8 at ≥ 10 GB, else 4), longest
    lines first so similar lengths share a call; a call that fails (out of memory) halves the group for the rest of
    the dub instead of going one line at a time. The program window says how many lines go at once.
  - Not done (ask first): fewer generation steps (16 instead of 32 ≈ 2× faster; on CPU it garbled a Russian word).
- **Not verified:** on the real card — how the floor sounds, and the new speed. Adam re-dubs the same video.

## ADR-037 — «Оригинал» listens to itself; names in the dub language's letters (2026-10-29)
- **Context:** after 0.10.3 Adam: "a lot better, but sentences are still cut off a lot; some words are left in
  English, or the dub says the English word in the copied voice". Measured (RESEARCH "how fast can a line be asked
  for"): OmniVoice garbles some lines even at −7% of its own length while others hold at 8 syllables/s — slips are
  word-dependent and partly random. Separately, the Claude prompt said "keep names, product names, code and acronyms
  as in the original", so Russian lines carried Latin words (Kay, MIB) that every voice reads in English.
- **Decision:**
  - The copied voice is hurried at most `clone.MAX_RATE` = 1.25× (Edge keeps the 1.6× cap); the 7-syllables/s floor
    stays.
  - Listen-back check: Whisper (`transcribe.reader`, same model as the transcription, on the card with the processor
    fallback) reads every new clip; `clone.heard_share` (words heard, and lowered by words heard that aren't in the
    text, e.g. English in the copied voice) < 0.8 → spoken again, up to `clone.TRIES` = 3, the last at
    the voice's own pace; the best try is kept. `clips_original_<lang>/check.json` keeps what was heard per line
    (for the next diagnosis); the program window says how many lines were redone / stay unclear.
  - Claude prompt v3: every word in the dub language's writing system (names by their established form or spelled
    as pronounced; Russian note: FBI → ФБР, Kay → Кей). Cached Claude translations are redone once.
- **Cost:** Whisper `small` on the card reads a short clip in well under a second; a 5-min video's ~110 lines add
  roughly a minute plus the redone lines.
- **Verified:** real OmniVoice + real Whisper (`small`, CPU) through `clone.synthesize`, 3 lines from an English
  reference: one line unclear on its first try, spoken again, all 3 heard (`check.json`), the window lines printed.
- **Not verified:** on Adam's card and his video. Not done: two voices at once (needs speakers — proposal in STATUS).

## ADR-038 — «Оригинал» knows who speaks: one voice sample per speaker, two voices at once (2026-10-29)
- **Context:** Adam (after 0.10.4, his `check.json` attached): asked to build the proposal — tell speakers apart, let
  lines of different people overlap as in the original (align.py never overlapped), copy each person from one longer
  sample (per-line 1-3 s references made the voice flip between "robot" and the real speaker).
- **Measured** (RESEARCH "Who speaks each line"): sherpa-onnx's full diarization (pyannote segmentation 3.0 + voice
  prints) merged two male voices that took turns 0.6 s apart. Voice prints of Whisper's lines, grouped, were exact
  with 3D-Speaker CAM++ `campplus_sv_zh_en_16k-common_advanced` (same speaker >= 0.71, different <= 0.19 on a 3-voice
  English + French test; WeSpeaker CAM++ / ResNet34 overlapped).
- **Decision:**
  - `speakers.py`: a voice print per line (>= 0.5 s) from the separated voice track; lines >= 1 s grouped by average
    linkage at cosine 0.45; shorter lines join the closest group; lines without a print go with the nearest line in
    time. Model: 28 MB from Hugging Face, run by `sherpa-onnx` (new dependency, wheels for Windows/Python 3.10-3.15;
    `deps.NATIVE` checks it loads). Only for «Оригинал» dubs, cached per set of lines (`work/<id>/speakers_*.json`);
    a failure never stops the dub (per-line samples, no overlap).
  - `clone.speaker_references`: each speaker's longest run of consecutive lines (pauses <= 1 s), up to 10 s (<= 15 s).
  - `align.build_track(speakers=...)`: a line waits only for the same speaker's previous line; unknown speakers wait
    for everyone. The Edge voice (one voice for all) never overlaps. `timing.json` lines carry `speaker`.
- **Verified:** real voice prints + OmniVoice + Whisper listener on CPU, the 3-voice test with Russian lines: speakers
  right, one reference per speaker, 7 of 8 lines heard exactly ("О какой…" heard "А какой…", one French-voiced line
  "Я тоже" → "Вято же" after 3 tries), every line on time. (With references whose text didn't match their audio the
  model spoke the reference text — "Turn. Buy." — so a reference's text must be what is said in it, as Whisper's is.)
- **Limit:** real crosstalk is mostly missing from Whisper's text (it writes the louder voice); dubbing both needs
  separating the voices first — not done.

## ADR-039 — Every dub its own library entry, with the exact time (2026-10-29)
- **Context:** Adam: "each time we dub a video, even the same video with the same settings, it should appear
  separately in the library, with the exact hour it was dubbed". Supersedes ADR-022's "the same choices replace".
- **Decision:** `pipeline.dub_id` ends with the dub's time (`…--ru-<hash6>-YYYYMMDD-HHMMSS`, `-2` if two finish in
  the same second); ids may be 96 characters (`app._ID`, phone routes). The grouped library stays (Adam's choice,
  ADR-027): a video's card shows the newest dub's date and time; the language tags' tooltip and «Другие озвучки этого
  видео» list each dub with its date and time; the watch page shows it too (`dateLabel` = date + hh:mm).

## ADR-040 — Soft line edges in the dub track (2026-10-29)
- **Context:** Adam: "very rough chops between sentences, harsh on the ear (the transitions between talking and
  silence)". Lines were cut at 1% of their peak with 30 ms kept, no fades; the background dropped in 20 ms.
- **Decision:** every line fades in (15 ms) and out (80 ms, raised cosine) and keeps 120 ms of its quiet tail, which
  may run under the next line (placement still uses the speech's end). The voice-free background ducks with 80 ms
  attack / 800 ms release, ratio 4.
- **Not verified:** by ear on Adam's PC.


## ADR-044 — 0.12.0 reverted (2026-10-30)
- **Context:** Adam merged 0.12.0 (PR #22: ADR-041 one library card per dub, ADR-042 foreign-line check + Claude
  prompt v4, ADR-043 «Оригинал» accent fix by voice conversion), then: "I don't like that, let's go back one merge."
- **Decision:** revert the whole merge; ship it as 0.12.1 (PCs update only to a higher version, ADR-024). ADR-027's
  grouped library and the 0.11.0 «Оригинал» apply again. The texts of ADR-041…043 are in git history (PR #22); the
  measurements stay in RESEARCH. PCs that already fetched the accent converter keep its files (unused, ~1 GB in the
  Hugging Face cache, `models--ResembleAI--chatterbox`).
