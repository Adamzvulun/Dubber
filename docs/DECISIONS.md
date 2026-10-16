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

## ADR-006 — Claude translation uses `claude-opus-5-5` by default (2026-10-16)
- **Context:** Optional paid translator. A cheaper model was considered; the model choice is the user's call.
- **Decision:** Default `claude-opus-5-5` at effort `low`, structured JSON output (same line count guaranteed by
  schema + count check + retry in halves), server-side refusal fallback. Override with `DUBBER_CLAUDE_MODEL`.
- **Consequences:** ~$0.05–0.20 per 10-minute video. Only used when `ANTHROPIC_API_KEY` is set.

## ADR-007 — Web UI with Gradio, designed for an older non-technical Russian reader (2026-10-16)
- **Decision:** One column, 18px+ text, one big primary action, PT Sans / PT Serif (ParaType fonts made for Cyrillic),
  calm slate + blue palette, all text in Russian, errors that say what to do. Result video hidden until it exists.
- **Consequences:** No custom frontend to maintain; Gradio gives progress bar, player and downloads for free.
