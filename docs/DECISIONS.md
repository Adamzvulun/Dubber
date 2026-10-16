# Decisions (ADR log)

Newest at the bottom. Format: context → decision → consequences.

## ADR-001 — Run locally on the user's PC (2026-10-16)
- **Context:** YouTube blocks many datacenter IPs; hosting costs money; the user is one person.
- **Decision:** Local app, opened in the browser (Gradio on `127.0.0.1:7860`), one-click Windows launchers.
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
