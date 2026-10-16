# Dubber 🎙️ — any YouTube video → a dub in your language

Paste a YouTube link (speech in **any language**, even several in one video), pick one of **12 dub languages**
(Russian by default; English, Hebrew, Ukrainian, Spanish, French, German, Italian, Portuguese, Arabic, Chinese,
Japanese) and get back:
- **the same video with a voice-over** (original audio kept quietly underneath, and as a 2nd selectable track),
- **subtitles** in the dub language (`.srt`, also embedded in the MP4),
- **a transcript**, plus a bilingual original + translation transcript for studying.

Built for a Russian-speaking professional who learns from foreign videos. Runs on your own PC, free by default.
The website has a Russian/English interface switch; a running dub can be cancelled (and resumed later).
Russian user guide: [`docs/README.ru.md`](docs/README.ru.md). Design: [`docs/DESIGN.md`](docs/DESIGN.md).

![Dubber website](docs/images/site-home-light.png)

## How it works
```
YouTube ─yt-dlp─► video ─faster-whisper (language per stretch of speech)─► text ─Google/Claude─► translation
        ─edge-tts─► voice in the dub language ─align─► timed track ─ffmpeg─► dubbed MP4 + SRT + TXT
```
Details and tool research: [`docs/RESEARCH.md`](docs/RESEARCH.md). Why each choice: [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Install
Needs **Python 3.10+**, **ffmpeg** and an internet connection.

**Windows:** double-click `scripts\install_windows.bat` once, then `scripts\start_windows.bat` every time.

**macOS / Linux:**
```bash
./scripts/install.sh     # creates .venv, installs everything
./scripts/start.sh       # opens http://127.0.0.1:7860
```

Command line instead of the web page:
```bash
.venv/bin/python -m dubber.cli "https://www.youtube.com/watch?v=VIDEO_ID"            # → Russian
.venv/bin/python -m dubber.cli --lang he --voice female "https://youtu.be/VIDEO_ID"   # → Hebrew, female voice
```
Results go to `output/<video id>/` and appear in the website's library.

## Settings (optional, in a `.env` file next to this README)
| Variable | Default | Meaning |
|---|---|---|
| `DUBBER_WHISPER_MODEL` | `small` | `tiny`/`base` faster, `medium`/`large-v3` more accurate (GPU recommended) |
| `DUBBER_VOICE` | `ru-RU-DmitryNeural` | or `ru-RU-SvetlanaNeural` |
| `DUBBER_TRANSLATOR` | `auto` | `google` (free), `offline` (free, on this PC, lower quality), `claude` (best, paid); `auto` = Claude if a key is set, else Google with automatic offline fallback |
| `DUBBER_COOKIES` | – | path to a `cookies.txt` exported from your browser, if YouTube says "confirm you're not a bot" |
| `ANTHROPIC_API_KEY` | – | enables Claude translation (a few cents per video) |
| `DUBBER_CLAUDE_MODEL` | `claude-opus-5-5` | Claude model used for translation |
| `DUBBER_LANG` | `ru` | default dub language (`ru en he uk es fr de it pt ar zh ja`) |
| `DUBBER_KEEP_BACKGROUND` | `1` | `0` = only the dubbed voice, without the original sound underneath (also a switch on the website) |
| `DUBBER_MAX_SPEEDUP` | `1.6` | fastest the dub voice may speak (1.6 = 60% faster than natural) to keep the speaker's timing |
| `DUBBER_ORIGINAL_VOLUME` | `0.15` | loudness of the original under the dub |

## Development
```bash
.venv/bin/ruff check . && .venv/bin/pytest
```
Tests run offline (network services are stubbed). Project docs: [`docs/PLAN.md`](docs/PLAN.md) (roadmap),
[`docs/PROGRESS.md`](docs/PROGRESS.md) (log), [`kanban/`](kanban) (tasks), [`docs/SKILLS.md`](docs/SKILLS.md) (Claude skills),
[`CLAUDE.md`](CLAUDE.md) (rules for Claude Code sessions).

## Note
For personal, educational use. Respect YouTube's terms and creators' rights; don't redistribute dubbed copies.
