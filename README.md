# Dubber 🎙️ — English YouTube → Russian dub

Paste a YouTube link, get back:
- **the same video with a Russian voice-over** (original audio kept quietly underneath, and as a 2nd selectable track),
- **Russian subtitles** (`.srt`, also embedded in the MP4),
- **a Russian transcript**, plus a bilingual EN/RU transcript for studying.

Built for a Russian-speaking professional who learns from English videos. Runs on your own PC, free by default.
Russian user guide: [`docs/README.ru.md`](docs/README.ru.md). Design: [`docs/DESIGN.md`](docs/DESIGN.md).

![Dubber website](docs/images/site-home-light.png)

## How it works
```
YouTube ─yt-dlp─► video ─faster-whisper─► English text ─Google/Claude─► Russian text
        ─edge-tts─► Russian voice ─align─► timed track ─ffmpeg─► dubbed MP4 + SRT + TXT
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
.venv/bin/python -m dubber.cli "https://www.youtube.com/watch?v=VIDEO_ID"
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
| `DUBBER_KEEP_BACKGROUND` | `1` | `0` = only the Russian voice, without the original sound underneath (also a switch on the website) |
| `DUBBER_MAX_SPEEDUP` | `1.5` | max speed-up of Russian phrases to fit the timing |
| `DUBBER_ORIGINAL_VOLUME` | `0.15` | loudness of the English original under the dub |

## Development
```bash
.venv/bin/ruff check . && .venv/bin/pytest
```
Tests run offline (network services are stubbed). Project docs: [`docs/PLAN.md`](docs/PLAN.md) (roadmap),
[`docs/PROGRESS.md`](docs/PROGRESS.md) (log), [`kanban/`](kanban) (tasks), [`docs/SKILLS.md`](docs/SKILLS.md) (Claude skills),
[`CLAUDE.md`](CLAUDE.md) (rules for Claude Code sessions).

## Note
For personal, educational use. Respect YouTube's terms and creators' rights; don't redistribute dubbed copies.
