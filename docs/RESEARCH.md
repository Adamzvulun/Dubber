# Research — tools for YouTube → Russian dubbing

_Last updated: 2026-10-16_

## Goal
Paste a YouTube link → get the same video with a Russian voice track, Russian subtitles and a Russian transcript.
Runs on a home PC (no GPU assumed), free by default.

## Pipeline (industry-standard shape)
```
YouTube URL ──yt-dlp──► video.mp4 ──ffmpeg──► audio.wav
   ──faster-whisper──► English words with timings → sentence lines [{start, end, text}]
   ──translator──────► Russian segments (same timing)
   ──edge-tts────────► one Russian clip per line, measured, then re-spoken at a planned steady rate
   ──align───────────► silence trimmed, lines placed at the speaker's start times → russian_track.wav
   ──ffmpeg──────────► original audio ducked + Russian track + RU subtitles → dubbed.mp4
```

## Existing open-source projects (studied, not used directly)
| Project | Stack | Why we don't just use it |
|---|---|---|
| [YouDub-webui](https://www.opensourcealternatives.to/item/youdub-webui) | Whisper, VoxCPM2 voice clone, Demucs | Chinese-first, needs GPU, heavy |
| [Voice-Pro](https://themenonlab.blog/blog/voice-pro-open-source-voice-cloning-dubbing) | Gradio, yt-dlp, Demucs, Whisper | Huge feature surface, complex install for a non-technical user |
| [youtube-auto-dub](https://www.sourcepulse.org/projects/27531261) | yt-dlp, Whisper, Google Translate, Edge TTS, FFmpeg | Closest to our design; small project, we want Russian-first UX + our own tests |
| [Union tutorial](https://www.union.ai/blog-post/open-source-video-dubbing-using-whisper-m2m-coqui-xtts-and-sad-talker) | Whisper, M2M100, Coqui XTTS, SadTalker | Cloud/GPU oriented; Coqui (XTTS) company has shut down |
| [OmniVoice Studio](https://themenonlab.blog/blog/omnivoice-studio-open-source-local-dubbing-646-languages) | zero-shot voice cloning, 646 langs | Newer, heavier |

Conclusion: build a small, focused, well-tested tool from the same proven building blocks.

## Building blocks chosen
| Stage | Tool | Notes |
|---|---|---|
| Download | [yt-dlp](https://github.com/yt-dlp/yt-dlp) | De-facto standard. YouTube often blocks **datacenter IPs** — fine on a home PC. Keep yt-dlp updated (`pip install -U yt-dlp`). |
| Speech→text | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2 Whisper, ~4× faster than openai-whisper, int8 on CPU. Model `small` is a good CPU default; `medium`/`large-v3` with GPU. |
| Translation | [deep-translator](https://github.com/nidhaloff/deep-translator) Google backend — free default; [Claude API](https://docs.anthropic.com) (`claude-opus-5-5`, opt-in with a key) | LLM translation keeps context across segments and keeps sentences short enough to dub. |
| Offline translation | [NLLB-200 distilled 1.3B](https://huggingface.co/OpenNMT/nllb-200-distilled-1.3B-ct2-int8) (CTranslate2 int8, CC-BY-NC) | Automatic fallback for **any** language pair when Google refuses (ADR-016); 1.4 GB on first use. Replaced opus-mt-en-ru (English→Russian only). |
| Russian TTS | [edge-tts](https://github.com/rany2/edge-tts) | Free Microsoft neural voices: `ru-RU-DmitryNeural` (male), `ru-RU-SvetlanaNeural` (female). Needs internet. |
| Timing | ffmpeg `atempo` | Speed clips up (capped) to fit segment slots. Replaced by Edge TTS `rate` + a steady-pace planner (`timing.py`); `atempo` is now only a ≤1.1× correction. See "Dub timing". |
| Mixing/mux | [ffmpeg](https://ffmpeg.org) | Duck original audio, overlay Russian, embed soft subtitles (`mov_text`). |
| UI | [FastAPI](https://fastapi.tiangolo.com) + hand-built HTML/CSS/JS (`dubber/web/`) | Local website. Gradio was used first and replaced (ADR-010). Design: `docs/DESIGN.md`. |

## Alternatives kept for later
- **ElevenLabs Dubbing API** — best quality, keeps the speaker's own voice; ~$1+/min. (M4)
- **Silero / Piper / RHVoice** — fully offline Russian TTS, lower quality.
- **F5-TTS Russian / XTTS** — local voice cloning; needs a GPU.
- **Demucs** — separate voice from music so background music survives the dub. (M3)
- **WhisperX** — better word-level alignment.

## Findings from real tests in a cloud (datacenter) sandbox — 2026-10-16
- **YouTube** blocks downloads from datacenter IPs ("Sign in to confirm you're not a bot", then HTTP 403 on video data
  for mweb / web_embedded / web_safari / tv / android_vr clients). Browser cookies (`DUBBER_COOKIES`) fix it.
  The browser-based PO-token plugin needs a desktop display. Home connections are normally not affected.
- **yt-dlp** now requires a JavaScript runtime (deno) for YouTube; the `deno` PyPI package provides it.
- **Google Translate** (unofficial free endpoints) answers datacenter IPs with a robot-check page.
- **Helsinki-NLP opus-mt-en-ru** (ONNX, ~110 MB) works offline on CPU with onnxruntime; it stops after the first
  sentence of each input, so we feed it single sentences. Quality: understandable, often literal.
- **faster-whisper 1.2.1 + PyAV 19** are incompatible when loading files; passing decoded samples avoids it.
- **edge-tts** (aiohttp) ignores `HTTPS_PROXY`; pass `proxy=` explicitly.
- CPU speed (4 cores): Whisper small ≈ 0.5× real time; whole pipeline ≈ 1× real time.

## Dub timing ("isochrony") — research 2026-10-16
Adam's report from his PC: the dub's speed-ups/slow-downs don't follow the speaker; some sentences rush, others drag.

### Measured on our pipeline (synthetic 37 s English talk, offline translator, Dmitry voice)
| # | EN speech | RU natural | RU/EN | atempo applied |
|---|---|---|---|---|
| 0 | 10.8 s | 16.0 s | 1.48 | 1.48 |
| 1 | 11.0 s | 16.4 s | 1.50 | 1.50 (cap) |
| 2 | 5.4 s | 8.1 s | 1.48 | 1.48 |
| 3 | 4.0 s | 5.6 s | 1.40 | 1.40 |
| 4 | 6.0 s | 8.7 s | 1.46 | 1.25 (used a 1 s pause) |
Whole talk: 37.2 s English → 54.8 s natural Russian (**×1.47**). Root causes in the current code:
1. **Every line is squeezed at the cap.** Russian TTS runs ~1.4–1.5× longer, our cap is 1.5×, so nearly all clips are
   time-stretched by `atempo` at its limit. Wherever a line needs more than 1.5× it overflows and later lines are pushed
   back (drift → "dragging"). On a fast talker this cascades.
2. **The speed jumps from line to line** (1.25× next to 1.5×) because each unit gets its own factor → audible
   "rushing then relaxing".
3. **Units are too coarse and cut in the wrong places.** Whisper segments are 30-s-window chunks: here 4–11 s units that
   hold 2–4 sentences and cut mid-sentence ("spacing your practice over | days…"). Inside a unit the dub cannot pause
   where the speaker pauses, so it runs ahead or behind the speaker within the line.
4. **Segment bounds include silence.** Whisper segment times are imprecise (often start early / end late), so "slot"
   lengths are wrong by up to ~0.5 s.
5. **Time-stretching after synthesis** (`atempo`) sounds worse at 1.4–1.5× than asking the voice to speak faster.

### What the field does
- Amazon's automatic-dubbing research defines the goal as **isochrony**: dubbed speech matches the timing of the
  original *phrases and pauses*. Three levers, used together: (a) control translation verbosity, (b) **prosodic
  alignment** — split the translation at the same pauses as the source, (c) control TTS duration inside the TTS model
  rather than warping audio afterwards. ([Duration modeling of neural TTS for automatic dubbing](https://www.amazon.science/publications/duration-modeling-of-neural-tts-for-automatic-dubbing),
  [Prosodic alignment for off-screen automatic dubbing](https://cdn.amazon.science/55/a8/2d996d984f6b96842f13cbc19dd8/prosodic-alignment-for-off-screen-automatic-dubbing.pdf),
  [Improvements to prosodic alignment](https://www.amazon.science/publications/improvements-to-prosodic-alignment-for-automatic-dubbing))
  Off-screen dubbing (narrator / speaker not lip-synced — our case) has looser constraints than lip-sync.
- **Length-controlled translation with LLMs:** give the translator a budget derived from the source duration
  (syllables or phonemes) and re-ask until it fits — [Duration-based Translation, EMNLP 2025 demo](https://aclanthology.org/2025.emnlp-demos.37)
  (+24% speech overlap, same quality); [HOMURA, 2026](https://arxiv.org/html/2601.10187v1) (syllable budget, used in
  production at Bilibili per secondary sources); re-ranking candidates by duration — [IWSLT 2023](https://preview.aclanthology.org/setup/2023.iwslt-1.9).
- **Open-source dubbing tools** (pyvideotrans, VideoLingo) cap audio speed-up and note that fluctuating speed sounds
  unnatural; they also borrow silence between lines and shorten translations.
- **Word timing:** WhisperX / stable-ts papers: raw Whisper segment times are inaccurate; word timestamps + VAD fix
  boundaries ([WhisperX](https://www.isca-archive.org/interspeech_2023/bain23_interspeech.html),
  [stable-ts](https://pypi.org/project/stable-ts/2.13.0)). faster-whisper has `word_timestamps=True` built in.

### Verified here: Edge TTS speed control is exact and predictable
`edge_tts.Communicate(text, voice, rate="+40%")` (SSML prosody rate). Same Russian sentence:
+0% 5.62 s · +20% 4.68 s (×1.20) · +40% 4.03 s (×1.39) · +60% 3.53 s (×1.59) — Dmitry and Svetlana alike.
So duration ≈ natural ÷ (1 + rate): **one natural-speed pass tells us the exact rate each line needs**, and the
voice engine speeds up its own speech (no time-stretch artefacts).

### Found while implementing: Edge clips are padded with silence
Every Edge clip has ~0.25 s of silence before and ~0.9 s after the speech (also at faster rates). The old aligner
started every line ~0.25 s late and counted ~1.15 s of silence as speech — a one-word line ("Нет.") "lasted" 1.9 s.
(So the ×1.47 above overstates the real ratio a little.) Now trimmed (`align.trim_silence`).

### Edge TTS reliability (measured 2026-10-16)
`NoAudioReceived` for any text without letters/digits, and at random for normal text: 5/56 sequential requests
(~9%), 0/56 at concurrency 4 in another run — i.e. random, not load-related. Retries (6 attempts) make a per-line
failure ~1e-6; see `tts.py`.

### Result on the same test talk (implemented, 2026-10-16)
| | Before | After |
|---|---|---|
| Lines | 5 chunks of 4–11 s, one cut mid-sentence | 12 real sentences, speech-only bounds |
| Pace | 1.25–1.50× by time-stretching | 1.40–1.50× by the voice itself, steady |
| Start of each line | ~0.25 s late (clip padding) | on time (max 0.01 s) |
| End vs speaker | unmeasured inside chunks | within ±0.12 s on 8 of 12 lines; others end up to 0.9 s early |
| Time-stretched lines | all | none |

### Recommended approach (plan: `docs/PLAN.md` M3.5)
1. Units = real sentences/phrases built from **word timestamps**, with speech-only start/end; split long sentences at
   pauses ≥ ~0.4 s (prosodic alignment: split the Russian at the matching comma/word boundary).
2. **One steady pace per video**: base rate from the median RU/EN ratio, per-line rate allowed only within a narrow
   band around it and smoothed between neighbours — no more 1.25× → 1.5× jumps.
3. Speed via **Edge `rate`** (two passes), `atempo` only as a last small correction.
4. Use the pause after a line (minus a breath) before speeding up; never push later lines unless unavoidable.
5. Optional (Claude key): **length-budgeted translation** — "say this in ≤ N syllables" from the slot length, retry
   if the clip still doesn't fit. Free path: Google/offline output, rate control only.
6. A **timing report** per video (start offsets, rates used, overflow) saved with the output, so quality is measured.

## Every dub language: translation + timing QA — 2026-10-17
Adam re-dubbed his English+French video: the French part was "not translated half the time, the other half gibberish".

### Causes found
1. **Google refuses at random** (robot check / HTTP 429; from this sandbox ~2 of 3 requests, later all). One refusal
   switched the rest of the video to the **offline English→Russian model**, which turned French into gibberish.
2. **Mixed batches:** Google detects one language per request, so a French line inside an English batch could come
   back untranslated and be voiced as French.
3. **Stale transcripts:** videos transcribed by the forced-English Whisper kept their cache.
4. Found by this QA: language detection on 20-s pieces mostly hears the piece's start, so English lines after French
   were labelled French (→ per-region detection with Whisper `base`: 19/19 regions right).

### Fix (ADR-016)
Line language from Whisper (per speech region) → one-language batches → Google JSON endpoint with retries →
**NLLB-200 1.3B** (offline, any language pair, CTranslate2 int8, 1.4 GB on first use) when Google stays unavailable →
quality gate (untranslated or wrong-script line re-sent; else the job stops rather than voicing it). Lines already in
the dub language are kept. NLLB quirks handled: sentence-by-sentence; Chinese stopping at a comma → forced
continuation (`min_decoding_length` past the cut) and clause split; stray spaces before punctuation removed.

### QA run: real pipeline, 2 multilingual clips × 12 dub languages (Google blocked here → offline NLLB path)
Clips: 33 s English+French (bakery), 29 s English+Spanish+German (morning habits); synthetic voices, real Whisper,
real Edge voices. "Re-heard" = Whisper (target language) listening to the dub vs the intended text.

| Dub language | EN+FR clip: untranslated / re-heard / late lines / rate range | EN+ES+DE clip: untranslated / re-heard / late lines / rate range |
|---|---|---|
| ru | 0 / 99% / 0 / 1.15–1.60× | 0 / 93% / 0 / 1.12–1.28× |
| en | 0 / 100% / 0 / 0.90–1.02× | 0 / 97% / 0 / 0.90–1.01× |
| he | 0 / 95% / 0 / 1.10–1.50× | 0 / 94% / 0 / 1.24–1.40× |
| uk | 0 / 97% / 0 / 1.22–1.47× | 0 / 99% / 0 / 1.08–1.25× |
| es | 0 / 100% / 0 / 0.91–1.13× | 0 / 99% / 0 / 0.95–1.13× |
| fr | 0 / 100% / 0 / 0.93–1.14× | 0 / 97% / 0 / 0.95–1.15× |
| de | 0 / 98% / 0 / 1.00–1.24× | 0 / 100% / 0 / 1.05–1.29× |
| it | 0 / 100% / 0 / 1.01–1.26× | 0 / 99% / 0 / 1.20–1.42× |
| pt | 0 / 98% / 0 / 1.00–1.24× | 0 / 99% / 0 / 1.14–1.32× |
| ar | 0 / 100% / 0 / 1.27–1.43× | 0 / 97% / 0 / 1.30–1.47× |
| zh | 0 / 97% / 0 / 0.90–1.05× | 0 / 100% / 0 / 0.91–1.08× |
| ja | 0 / 94% / 0 / 1.06–1.22× | 0 / 96% / 0 / 0.97–1.20× |

Meaning, read line by line (all 24 dubs): correct in every language, with these offline-backup slips: Hebrew "flour"
→ "acid/vinegar" (חומצה/חומץ); Japanese "welcome back" → "seems you're back"; one Arabic word misspelled; the
speaker's gender isn't known to the translator (a woman speaking can come out masculine in Hebrew). One English line
was garbled by Whisper itself (two sentences merged), which every translation inherits. Google (primary on Adam's PC)
could not be exercised end-to-end here (429 on every try) — its client is covered by unit tests.

## Session 3 measurements — Hebrew voice, transcription, voice removal (2026-10-18)

### Hebrew pronunciation (Adam: "mispronounces almost every second word", e.g. יתר read "iter")
Method (all free, runs offline after downloads): 50 sentences with gold IPA readings incl. stress from the
[heb-g2p-benchmark](https://huggingface.co/spaces/Phonikud/heb-g2p-benchmark) (built around homographs); every
candidate speaks them; [renikud/whisper-he-ipa](https://huggingface.co/renikud/whisper-he-ipa) (converted to
CTranslate2 int8) writes down what it hears as IPA with stress; word error rate against the gold reading. The scorer
makes errors of its own, so only the comparison between candidates matters. Script: `tools/qa_hebrew_voice.py`.

| Candidate | Word errors incl. stress | Sounds only |
|---|---|---|
| Edge Avri (male), plain text — today | **0.231** | **0.174** |
| [Phonikud](https://huggingface.co/Phonikud) Piper voice + [renikud](https://huggingface.co/renikud/renikud) G2P (offline) | 0.233 | 0.184 |
| Edge Hila (female), plain text | 0.256 | 0.203 |
| Edge Avri + full niqqud from [phonikud-onnx](https://huggingface.co/Phonikud/phonikud-onnx) | 0.313 | 0.243 |
| Edge Avri + niqqud only on words without vowel letters (ambiguous ones like יתר) | 0.251 | 0.189 |

- **Edge reads niqqud badly**: Phonikud writes holam/qubuts before a plain vav (לִכְתֹּוב) and Edge then says
  "lixtov-ov"; even after moving the vowel onto the vav, vowelled text scored worse than plain text.
- **Adam's example is a spelling problem, not a voice problem:** Edge says יתר correctly ("yeter") in all 6 test
  contexts, both voices; the spelling **ייתר** (an extra yod) is read "yiter"/"iter" by both. The dub reads what the
  translation wrote. → Claude now gets a Hebrew spelling rule (`translate.SPEECH_NOTES`).
- Edge's remaining errors are homographs (חיה, בירה, שמתי), grammatical gender that spelling doesn't show
  (לך lax/lexa), and English brand names. No free engine did better; the Phonikud voice ties on accuracy but sounds
  less natural and is non-commercial (CC-NC).
- Russian: Claude is asked to write "ё" (Edge reads "е" otherwise, e.g. всё/все).

### Transcription on real recorded speech (FLEURS dev, 12 clips per language, Dubber's own `transcribe()`)
| Whisper | English | French | Hebrew | EN+FR mixed (en / fr) | CPU s per audio minute* |
|---|---|---|---|---|---|
| small (default) | 0.101 | 0.140 | 0.811 → **0.757** | 0.199 (0.272 / 0.146) → **0.153** (0.171 / 0.140) | 26–39 |
| large-v3-turbo | 0.115 | 0.070 | 0.709 → **0.631** | 0.137 → 0.137 (0.212 / 0.083) | 34–90 |
| medium | 0.166 | — | — | — | 79 |
→ = after the two fixes below. *4 vCPUs shared with other jobs. Hebrew WER is inflated by spelling variants.
- **Bug 1: stray language guesses.** The per-region detector (Whisper base, small too) called clear Hebrew regions
  Italian 0.74 / French 0.68 / Latvian 0.50 → those regions were transcribed as Italian/French gibberish and then
  "translated". Fix: `transcribe.video_languages` — a language counts only if it fills ≥ 15 % of the speech (summed
  probabilities) or one ≥ 2 s region is ≥ 0.9 sure; every region gets the likeliest of those.
- **Bug 2: first words of a run lost.** Runs were cut with 0.2 s margins; the first words after a language switch
  were dropped. Fix: margins up to 1 s, never past the middle of the pause.
- **turbo not made the default:** better on French/Hebrew, but it skipped a whole English sentence in both runs and
  hallucinated "The / The / You" at the end of the English file; ~1.5× slower. English is the main source language.

### Voice removal (Demucs v4 `htdemucs`, ONNX: [StemSplitio/htdemucs-onnx](https://huggingface.co/StemSplitio/htdemucs-onnx), MIT)
- Test mix: Edge English voice over a generated music bed (30 s). Background output: Whisper finds **no words**;
  level unchanged (−20.6 dB music in, −20.6 dB background out).
- Speed on this sandbox (4 vCPUs, partly busy): ~1× real time (114 s for 120 s) → ≈ 10 min per 10-min video while busy, **65 s for 120 s (≈ 5.4 min per 10 min) on the idle 4 vCPUs**;
  the model card reports 0.2× real time on an Apple M4 Pro. Memory stays low (files on disk, 7.8-s windows).
- End-to-end CLI dub (`--remove-voice`, offline translator): Russian track = Russian voice + music, no English left
  (Whisper forced to English only re-translates the Russian); original English track and Russian subtitles intact.

## Hosting on Hugging Face Spaces — research 2026-10-18 (ADR-023)
Question (Adam): could Dubber run as a Hugging Face Space instead of on the home PC?

| Topic | What Spaces offers (official docs, Oct 2026) | What it means for Dubber |
|---|---|---|
| Price | Gradio/Docker Spaces **require a PRO plan ($9/month)** to create; free accounts only get 2 ZeroGPU Gradio Spaces. CPU Basic hardware itself has no hourly fee | ~$9/month minimum |
| Hardware | CPU Basic 2 vCPU / 16 GB RAM / 50 GB disk; CPU Upgrade 8 vCPU / 32 GB at $0.03/h; T4 GPU $0.40/h | 2 vCPU: Whisper `small` + Demucs slower than the PC (≈ 0.5–1× real time and more) |
| GPU for free | ZeroGPU: **Gradio SDK only**, daily per-visitor quota (~minutes) | would need a Gradio rewrite of our UI (we left Gradio, ADR-010) — no |
| App type | Docker SDK runs any web server; port 7860 is the default (also ours) | `dubber.app` runs as-is in a Dockerfile (Python + ffmpeg + deno) |
| Storage | Disk is **ephemeral** (lost on restart/sleep); persistence = attached **Storage Bucket** ($18/TB/month private) | library + `work/` cache need a bucket mounted as `output/`, `work/`; cents per month at our size |
| Sleep | free hardware sleeps after ~48 h unused, wakes on visit (cold start: models re-download unless cached in the bucket) | first dub after a pause is slower |
| Secrets | Space Secrets → env vars | Claude key as `DUBBER_CLAUDE_KEY`-style secret, not in `.env` |
| Access | Private Space: only signed-in owner/collaborators; Protected (PRO): code private, app public | public app = anyone could spend the Claude key; private needs every user to have an HF account and log in |
| Network | outbound only ports 80/443/8080 | fine: Edge TTS, Anthropic, Google, Hugging Face are all 443 |

**The blocker — YouTube.** YouTube answers datacenter IPs with "Sign in to confirm you're not a bot"; users report
exactly this on Hugging Face's own `openai/whisper` Space, and cookies did not always help (and risk the Google
account). This is the same block we see in the cloud sandbox, and it applies to every cloud host, not just HF.
Google Translate also rate-limits datacenter IPs (HTTP 429 here) → the offline NLLB backup (1.4 GB download per cold
start) or Claude would do the translating.

**Verdict:** not a fit while the input is a YouTube link. It becomes worth a test if the website accepts an
uploaded video file (PLAN M3 idea) — then: Docker Space + PRO + a private bucket, Claude key as a Space secret, a
login in front. Until then the home PC is free, faster and already works.

Sources: [Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview),
[Spaces storage](https://huggingface.co/docs/hub/spaces-storage), [pricing](https://huggingface.co/pricing),
[ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu.md),
[openai/whisper Space bot-check report](https://huggingface.co/spaces/openai/whisper/discussions/121).

## VoiceStudio / OmniVoice — open-source "ElevenLabs" — research 2026-10-19 (ADR-028)
Adam asked whether [debpalash/voicestudio](https://github.com/debpalash/voicestudio) can improve or replace parts of
Dubber. Read the repo (cloned at its 2026-10-19 head) and measured its voice model here.

**What it is.** An Electron desktop app + FastAPI backend (AGPL-3.0) for voice cloning, voice design and video
dubbing (separation, WhisperX, diarization, LLM translation, per-line cloned TTS, "Smart Fit" timing). Its default
voice is [k2-fsa/OmniVoice](https://huggingface.co/k2-fsa/OmniVoice): 0.6B parameters, zero-shot cloning from a 3–10 s
clip, 646 languages, 24 kHz; `pip install omnivoice` (code Apache-2.0, **weights CC-BY-NC** — personal use only).
`generate()` takes `duration=` (speak the line in exactly N seconds) and `speed=`. Training data per language
(`docs/languages.md` there): ru 20 338 h, en 206 061 h, es/fr/de/pt/ja/zh ≥ 9 000 h, uk 1 852 h, ar (MSA) 1 484 h,
**he 13.4 h**. The project says the model needs a GPU with ≥ 6 GB VRAM; a CPU build exists but is "slower".

**Measured here** (4 CPU cores, PyTorch 2.14 CPU, `omnivoice` 0.2.1, float32; English Edge voice as the reference,
cloned into Russian and Hebrew lines; intelligibility = Whisper `small` transcribing the result back):

| Setting | Compute per ~3.5 s line | × real time |
|---|---|---|
| default (32 steps) | 68–77 s | **≈ 20×** |
| 16 steps | 33–35 s | ≈ 10× (Russian: one word garbled) |
| 4 lines in one call | 254 s for 12.7 s | ≈ 20× — batching gives nothing on CPU |
| `duration=3.0` | 3.19 s out | follows the target (≥ 4.5 s gets trimmed by its silence post-processing) |

- **Russian:** transcribed back as the text (same as Edge). Cloned voice keeps the reference timbre.
- **Hebrew:** clearly worse than Edge — e.g. "היום הנהר עליהם, איך לעפות להם פושת" for "היום אני אראה לכם איך לאפות
  לחם פשוט"; Edge's Avri came back nearly right. Matches the 13.4 h of Hebrew training data.
- **CPU cost for Dubber:** a 10-min video has ≈ 6–8 min of speech → **≈ 2–2.5 h** of voice generation on 4 cores (vs
  seconds with Edge). On an NVIDIA GPU (project's numbers: real-time factor down to 0.025) it would be minutes.

**In Dubber (v0.7.0, ADR-028) — real CPU dub of a 2-speaker clip:** per-line references keep each speaker (male lines
94–121 Hz, female 176–211 Hz; Whisper reads all lines back). OmniVoice's `RuleDurationEstimator` boosts estimates under
50 tokens (2 s) with a power curve (`low_threshold`, `boost_strength=3`): "Прекрасно." 1.27 s instead of 0.51 s.
Planning the pace from boosted estimates made the dub 1.52× fast; with `low_threshold=None` it is 1.02× and lines
match the speaker's length. `duration=` is followed closely (asked 2.06 s → 2.01 s spoken, after its silence trim).

**Ideas in VoiceStudio worth borrowing without its voice model** (its `docs/competitive-analysis.md`,
`backend/services/fit_planner.py`):
1. **Check the dub by listening to it** — transcribe each dubbed line back and flag/redo lines whose words don't match
   (catches TTS glitches and mispronunciations; we did exactly this above).
2. **Slow the video slightly instead of rushing the voice** — when a line needs > 1.2× speed-up, split the stretch
   between voice (≤ 1.5×) and a per-line video slow-down (≤ 2×). Needs a video re-encode (minutes on CPU).
3. **A voice per speaker** — diarization (pyannote, needs PyTorch) to give each speaker their own (male/female) voice.

## TikTok, Instagram, Facebook without a login — research 2026-10-28 (ADR-031, ADR-032)
Adam: the cookies-file route (browser extension → file → upload) is too much work for the user; find a way to get
these videos **without logging in**. Findings (the sandbox can't reach the three sites, so this is from sources and
yt-dlp's code, not from live downloads):

| Site | Without a login | What it needs | Confidence |
|---|---|---|---|
| **TikTok** | public videos: yes | yt-dlp's TikTok extractor requests pages with `impersonate=True`; without **curl_cffi** TikTok answers with a bot-challenge page (several projects hit exactly this and fixed it by installing `yt-dlp[curl-cffi]`) | high |
| **Instagram** | public reels/posts: yes, with limits | yt-dlp (2026.10.26, `extractor/instagram.py`) sends the logged-out GraphQL query `PolarisLoggedOutDesktopWWWPostRootContentQuery` **only `if self._can_impersonate`**; without curl_cffi it skips it and Instagram redirects to the login page. yt-dlp maintainer in issue 17074 (2026-06-29): without cookies the curl-cffi dependency is required. Instagram rate-limits anonymous access per IP ("exceeded the rate-limit for accessing posts anonymously") — fine for a few videos from a home connection, not for bulk | medium (unverified live) |
| **Facebook** | public videos/reels: yes | plain yt-dlp; reels can use impersonation too | medium |
| any | private / followers-only / age-gated posts | a login (cookies) — no way around it | high |

Ways considered to avoid the login entirely:
1. **Install yt-dlp's `curl-cffi` extra** (browser TLS fingerprint) — **chosen** (ADR-032). Free, no user effort,
   Windows wheels for Python 3.10–3.14 (curl_cffi 0.17, abi3), verified that yt-dlp lists `curl_cffi` impersonation
   targets after install. Kept fresh with yt-dlp (launcher refresh every 3 days, updater).
2. **Third-party download services** (snapinsta-type sites, tikwm.com, public cobalt instances) — rejected: privacy
   (the user's links go to unknown servers), ads/bot checks, terms of the services; cobalt's public instances are
   bot-protected and "not meant for other projects without permission".
3. **Self-hosted cobalt** (Docker image `ghcr.io/imputnet/cobalt`) — rejected: needs Docker on the user's PC, its
   extractors break as often as yt-dlp's, a Japanese review (2026) says the main branch stalled since April 2026.
4. **Reading the user's Chrome/Edge logins directly** (`--cookies-from-browser`) — impossible on Windows: Chrome 127+
   app-bound encryption ("v20" cookies can't be decrypted by another program), the database is locked while the
   browser runs; Firefox works but the users have Chrome/Edge.
5. **Easier login if no-login isn't enough — not built, offer to Adam:** a «Войти в Instagram» button that opens
   Edge (always on Windows) with its **own** profile folder in the program (`--user-data-dir=<Dubber>\browser`) and
   `--remote-debugging-port`; the user logs in once in that window, Dubber reads the cookies over the DevTools
   protocol (`Network.getAllCookies`, returns decrypted HttpOnly values) and writes `cookies.txt`. Chrome 136+ only
   blocks remote debugging for the *default* profile, a custom `--user-data-dir` is allowed (Chrome developer blog,
   "Changes to remote debugging switches"). No extension, no file handling; needs Edge/Chrome path discovery, a
   free port, closing the window, and care that the port only listens on 127.0.0.1.

Sources: yt-dlp issue 17074 "Instagram sent an empty media response WITHOUT cookies"
(github.com/yt-dlp/yt-dlp/issues/17074), yt-dlp `extractor/instagram.py` and `extractor/tiktok.py` (2026.10.26),
projects fixing TikTok with curl_cffi (e.g. github.com/hypit-ai/hypit/issues/381), Chrome blog
developer.chrome.com/blog/remote-debugging-port, cobalt API docs (github.com/imputnet/cobalt/blob/main/docs/api.md),
yt-dlp issue 7271 / 10927 (Chrome cookies on Windows).

## OmniVoice: how fast can a line be asked for? — measured 2026-10-29 (ADR-036, ADR-037)
Adam's «Оригинал» dubs: sentences "swallowed or warped", then (0.10.3, floor 7 syllables/s) "still cut off a lot".
Real `omnivoice==0.2.1` on CPU (32 steps), an English Edge reference (en-US-AndrewNeural, 6 s), six Russian lines,
each at its own length and at 5/6/7/8 syllables per second (+0.2 s); Whisper `small` reads every clip back
(`tools`-style script kept in the session scratchpad, not in the repo).

| line (syllables) | own length | 5/s | 6/s | 7/s | 8/s |
|---|---|---|---|---|---|
| Прекрасно. (3) | "Рекрасно" (Whisper) | ok | ok | ok | ok |
| Ладно, слушай внимательно. (8) | ok | ok | ok | ok | ok |
| Мы не знаем, откуда они прилетели. (13) | ok | ok | ok | ok | ok |
| Кей, ты видел, что он сделал с машиной? (11) | ok | ok | **"КТ-Виддл. Стон…"** | **"…видеостон…"** | **"Кейт и Ведерстон…"** |
| Никому ни слова об этом, понятно? (12) | ok | ok | ok | ok | ok |
| У тебя есть пять секунд… я стреляю. (19) | ok | ok | ok | ok | ok |

- The model's own estimate for "Кей…" was 2.18 s; asked for 2.03 s (−7%) it already garbled the middle. Other lines
  held at 8/s. Slips depend on the words (and the model samples), so **no speed limit alone prevents them**.
- `duration=` is followed within ~0.2 s (its 0.1 s padding on each side). Whisper on a lone word can drop its first
  sound ("Рекрасно"), so the listen-back match forgives small slips (`clone.SAME_WORD` = 0.85 similarity).
- Decision (ADR-037): hurry the copied voice at most 1.25× and listen to every clip; garbled lines are spoken again,
  the last try at the voice's own pace.

## Who speaks each line — measured 2026-10-29 (ADR-038)
Test conversation (session scratchpad, not in the repo): 8 turns of three Edge voices — Andrew (en, male), Ava (en,
female), Henri (fr, male) — 0.6-s pauses, turn 7 starting 1 s before turn 6 ends (crosstalk). `sherpa-onnx` 2.0.1.

- **Full diarization** (pyannote segmentation 3.0 + voice prints + clustering, thresholds 0.5/0.7/0.9): never right.
  Andrew's and Henri's adjacent turns (6.9-9.8 s, 10.4-13.8 s) became one segment with every voice-print model
  (3D-Speaker ERes2Net, WeSpeaker CAM++, 3D-Speaker CAM++ advanced); WeSpeaker CAM++ also merged everyone at 0.7.
- **Voice prints of the turns themselves** (what Dubber has: Whisper's lines), cosine similarity, crosstalk turns
  left out of the min/max:

| model (sherpa-onnx `speaker-embedding-models`) | same speaker, min | different, max |
|---|---|---|
| 3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k | 0.58 | 0.26 |
| wespeaker_en_voxceleb_CAM++ | 0.40 | 0.79 |
| **3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced** (28 MB) | **0.71** | **0.19** |
| nemo_en_titanet_small | 0.60 | 0.30 |
| wespeaker_en_voxceleb_resnet34_LM | 0.79 | 0.61 |

- `speakers.assign` with the CAM++ advanced model: all 8 turns + two shorter cut-outs (1.1 s, 0.6 s) right, 1.8 s on
  2 CPU threads. The overlapped turns still group right (their prints stay closest to their own speaker).

## Foreign lines inside a video — measured 2026-10-30 (ADR-042)
_Built in 0.12.0, reverted in 0.12.1 at Adam's request — the measurements stay valid._

Adam's `check.json` (Men in Black): Spanish lines in the English film were transcribed as English and Claude spelled
the nonsense out in Russian letters ("Йо, хани, че, хайста…"). Test clip (sandbox CPU): Edge `en-US-AndrewNeural`
lines with three short `es-MX-JorgeNeural` lines between them ("¿Qué pasa?" 1.3 s, "Oye, hermano." 1.9 s, "Sí, sí,
vámonos." 2.5 s), clean and under pink noise (−10 / −3 dB):

| clip | "base" detector (what decided) | runs before | "small" on the same region | runs after |
|---|---|---|---|---|
| clean | es 0.33 / es 0.44 / es 0.95 | en, es, en, es, en, es, en (Spanish found) | — | same |
| noise −10 dB | es 0.53 / pl 0.20 / es 0.69 | **all English** | en 0.34 / ta 0.27 / **es 0.88** | the 2.5-s line Spanish |
| noise −3 dB | ru 0.39 / en 0.14 / pt 0.24 | **all English** | en 0.44 / en 0.23 / **es 0.93** | the 2.5-s line Spanish |

Spanish was too small a share of the speech to count as a video language (`MAIN_SHARE`), and no region was sure
enough (`SURE`) for a quote. Whisper `small` (already loaded to transcribe) is much surer on the longer line, so a
region of ≥ 1.5 s whose best "base" guess is not a video language is heard again by `small`, and kept in the language
it is ≥ 0.85 sure of; transcribed in Spanish it reads "Sí, sí, vámonos." exactly. Lines of ~1–2 s stay ambiguous to
both models (no fix from the detector): the Claude prompt (v4) now says such a nonsense line is usually a misheard
phrase in another language — translate its meaning, never spell it out.

## The English accent in Russian «Оригинал» dubs — measured 2026-10-30
_Option (b) was built in 0.12.0 and reverted in 0.12.1: Adam didn't like the result. The code is in git (PR #22)._

Adam: with «Оригинал» the Russian dub sometimes has an American accent; the dub must stay the speaker's own voice.
Cause: OmniVoice's README says cross-lingual cloning carries the reference language's accent; its `instruct`
accents exist only for English speech, so no setting removes it. Test (sandbox CPU): "speaker" = Edge
`en-US-AndrewNeural` (7.7-s English reference), 4 Russian lines; native Russian = Edge `ru-RU-DmitryNeural`; voice
conversion = Chatterbox VC (Resemble AI, MIT, `s3gen` 1 GB; runs with torch 2.15 installed `--no-deps`). Scores:
Whisper `small` language confidence for "ru" (accent proxy), share of words heard, CAM++ voice-print cosine to the
speaker on another English sentence (the speaker vs himself = 0.89; vs the Russian Edge voice = 0.35).

| version | ru | heard | like speaker | like Edge ru |
|---|---|---|---|---|
| today: OmniVoice cloned from the English reference | 0.82 (one line 0.43, "шесть щенков" → "6 шинков") | 0.95 | **0.75** | 0.33 |
| OmniVoice cloned from a converted Russian reference (Edge ru → speaker) | 0.995 | 1.0 | 0.13 | 0.25 |
| A: OmniVoice with a native Russian reference, then converted to the speaker | **0.99** | 0.96 | 0.67 | 0.39 |
| B: Edge Russian line converted to the speaker | 0.98 | 1.0 | 0.65 | 0.44 |

Conversion after speaking keeps native pronunciation and most of the voice (0.65-0.67 vs 0.75); feeding a
converted sample to OmniVoice loses the voice. CPU: ~15 s per 4-s line for the conversion (a card: well under 1 s).
Listening page for Adam: https://claude.ai/artifact/A7T3H47gXbeanCu7nEPwda (synthetic voices only).

## Phone version and NVIDIA libraries — notes 2026-10-28/29 (ADR-033, ADR-034, ADR-035)
- **Reaching a home PC from a phone, no accounts for users:** Tailscale works anywhere but needs an app + sign-in on
  every PC and phone (rejected: Adam wants one click). Cloudflare **quick tunnels** (`cloudflared tunnel --url …`)
  need no account and give a random `https://<words>.trycloudflare.com` per start — offered "for testing", no uptime
  promise, 100 MB request bodies; the address is published through a Worker + KV mailbox on Adam's free account. If
  they prove flaky: named tunnels under that account (need a domain).
- **iPhone home-screen web apps** don't share Safari's storage → the household token lives in the app's path
  (`/p/<token>/`), not in localStorage. Android's `share_target` gives Share → Дубляж; iOS has no share target for
  web apps (a «Вставить» button reads the clipboard instead).
- **Whisper on NVIDIA:** ctranslate2 4.5+ needs cuBLAS 12 + cuDNN 9; on Windows the pip packages
  `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` put the DLLs in `site-packages/nvidia/*/bin` (faster-whisper README).
- **OmniVoice speed:** ~20× slower than real time on 4 CPU cores (measured 0.7.0); Task Manager's "3D" GPU graph
  doesn't show CUDA work (pick "Cuda"), so "the card is idle" there proves nothing. The model is 3.3 GB on Hugging
  Face (≈ 1.2 GB on the card in float16).

## Risks
- YouTube anti-bot changes → keep yt-dlp updated; cookies-from-browser fallback (see `youtube-downloader` skill references).
- edge-tts is an unofficial client of a Microsoft service — may break; Silero offline fallback planned.
- Long videos on CPU: transcription is the slow part (≈ 0.3–1× real time with `small` int8).
- Legal: personal, educational use of the dubbed copies only; no redistribution.
