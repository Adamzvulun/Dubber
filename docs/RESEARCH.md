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
| Offline translation | [Helsinki-NLP opus-mt-en-ru](https://huggingface.co/Helsinki-NLP/opus-mt-en-ru) via [Xenova ONNX export](https://huggingface.co/Xenova/opus-mt-en-ru) + onnxruntime | Automatic fallback when Google refuses. ~110 MB, no PyTorch. Literal quality; translate one sentence at a time. |
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

## Risks
- YouTube anti-bot changes → keep yt-dlp updated; cookies-from-browser fallback (see `youtube-downloader` skill references).
- edge-tts is an unofficial client of a Microsoft service — may break; Silero offline fallback planned.
- Long videos on CPU: transcription is the slow part (≈ 0.3–1× real time with `small` int8).
- Legal: personal, educational use of the dubbed copies only; no redistribution.
