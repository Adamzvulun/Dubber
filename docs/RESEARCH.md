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

## Risks
- YouTube anti-bot changes → keep yt-dlp updated; cookies-from-browser fallback (see `youtube-downloader` skill references).
- edge-tts is an unofficial client of a Microsoft service — may break; Silero offline fallback planned.
- Long videos on CPU: transcription is the slow part (≈ 0.3–1× real time with `small` int8).
- Legal: personal, educational use of the dubbed copies only; no redistribution.
