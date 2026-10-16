# Research — tools for YouTube → Russian dubbing

_Last updated: 2026-10-16_

## Goal
Paste a YouTube link → get the same video with a Russian voice track, Russian subtitles and a Russian transcript.
Runs on a home PC (no GPU assumed), free by default.

## Pipeline (industry-standard shape)
```
YouTube URL ──yt-dlp──► video.mp4 ──ffmpeg──► audio.wav
   ──faster-whisper──► English segments [{start, end, text}]
   ──translator──────► Russian segments (same timing)
   ──edge-tts────────► one Russian clip per segment
   ──align (atempo)──► clips fitted to timing → russian_track.wav
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
| Translation | [Claude API](https://docs.anthropic.com) (Haiku) — optional; [deep-translator](https://github.com/nidhaloff/deep-translator) Google backend — free default | LLM translation keeps context across segments and can keep sentences short enough to dub. |
| Russian TTS | [edge-tts](https://github.com/rany2/edge-tts) | Free Microsoft neural voices: `ru-RU-DmitryNeural` (male), `ru-RU-SvetlanaNeural` (female). Needs internet. |
| Timing | ffmpeg `atempo` | Russian is ~10–20% longer than English; speed clips up (capped) to fit segment slots. |
| Mixing/mux | [ffmpeg](https://ffmpeg.org) | Duck original audio, overlay Russian, embed soft subtitles (`mov_text`). |
| UI | [Gradio](https://gradio.app) | Local web page, built-in progress bar, video player, file downloads. |

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

## Risks
- YouTube anti-bot changes → keep yt-dlp updated; cookies-from-browser fallback (see `youtube-downloader` skill references).
- edge-tts is an unofficial client of a Microsoft service — may break; Silero offline fallback planned.
- Long videos on CPU: transcription is the slow part (≈ 0.3–1× real time with `small` int8).
- Legal: personal, educational use of the dubbed copies only; no redistribution.
