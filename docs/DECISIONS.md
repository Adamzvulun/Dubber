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
