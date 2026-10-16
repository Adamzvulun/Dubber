---
name: ffmpeg-dubbing
description: The ffmpeg/ffprobe recipes Dubber relies on — extracting audio for Whisper, speeding speech up with atempo, ducking and mixing a voice-over, muxing multiple audio tracks and soft subtitles into MP4, burning subtitles, and inspecting results. Use when writing or debugging media code in dubber/media.py, align.py or mux.py.
---

# ffmpeg recipes for dubbing

Always call through `dubber/media.py` (`run_ffmpeg`, `probe`, `decode_audio`, `write_wav`) so errors are raised with stderr.

```bash
# Audio for Whisper: mono 16 kHz PCM
ffmpeg -i in.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav

# Speed speech up without changing pitch (atempo accepts 0.5–100; chain for extreme values)
ffmpeg -i clip.mp3 -af atempo=1.25 fast.wav

# Duck original to 15% and lay the Russian track over it; output length = video length
ffmpeg -i video.mp4 -i ru.wav -i ru.srt \
  -filter_complex "[0:a]volume=0.15[bg];[1:a]apad[fg];[bg][fg]amix=inputs=2:duration=first:normalize=0[dub]" \
  -map 0:v:0 -map "[dub]" -map 0:a:0 -map 2:s:0 \
  -c:v copy -c:a aac -b:a 160k -c:s mov_text \
  -metadata:s:a:0 language=rus -metadata:s:a:1 language=eng -metadata:s:s:0 language=rus \
  -disposition:a:0 default -disposition:a:1 0 -movflags +faststart out.mp4

# Burn subtitles into the picture (re-encodes video; needs libass)
ffmpeg -i out.mp4 -vf "subtitles=ru.srt:force_style='FontSize=22'" -c:a copy burned.mp4

# Inspect
ffprobe -v error -show_entries stream=index,codec_type,codec_name:stream_tags=language -of compact out.mp4

# Synthetic test media (offline tests)
ffmpeg -f lavfi -i testsrc=size=320x240:rate=25:duration=6 -f lavfi -i sine=frequency=300:duration=6 \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest sample.mp4
```

Gotchas
- `amix` normalizes (lowers) volumes by default → always `normalize=0`.
- `-c:v copy` keeps quality and is fast, but the source codec must be MP4-compatible (download prefers H.264).
- `mov_text` is the only subtitle codec MP4 supports; SRT goes in, `mov_text` is stored.
- lavfi `sine` has amplitude 1/8 — mean |x| ≈ 0.08; use that when asserting on test audio energy.
