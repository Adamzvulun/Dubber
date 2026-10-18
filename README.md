# Dubber 🎙️ — any YouTube video → a dub in your language

Paste a YouTube link (speech in **any language**, even several in one video), pick one of **12 dub languages**
(Russian by default; English, Hebrew, Ukrainian, Spanish, French, German, Italian, Portuguese, Arabic, Chinese,
Japanese) and get back:
- **the same video with a voice-over** (original audio kept quietly underneath, and as a 2nd selectable track),
- **subtitles** in the dub language (`.srt`, also embedded in the MP4),
- **a transcript**, plus a bilingual original + translation transcript for studying.

Made for people who learn from videos in other languages. Runs on your own PC, free by default.
The website has a Russian/English interface switch; a running dub can be cancelled (and resumed later).
Russian user guide: [`docs/README.ru.md`](docs/README.ru.md). Design: [`docs/DESIGN.md`](docs/DESIGN.md).

![Dubber website](docs/images/site-home-light.png)

## How it works
```
YouTube ─yt-dlp─► video ─faster-whisper (language per stretch of speech)─► text ─Google/Claude─► translation
        ─edge-tts─► voice in the dub language ─align─► timed track ─ffmpeg─► dubbed MP4 + SRT + TXT
        (optional: Demucs removes the original voice, keeping music and sounds under the dub)
```
Details and tool research: [`docs/RESEARCH.md`](docs/RESEARCH.md). Why each choice: [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Install
Needs **Python 3.10+**, **ffmpeg** and an internet connection.

**Windows:** double-click **`Start Dubber.cmd`**. The first run installs Python and ffmpeg (winget) and the
components (10–15 min, log in `install.log`), puts a «Дубляж видео» shortcut with the program's icon on the desktop
and in the Start menu, and starts the program; later runs just start it (`scripts/windows/dubber.ps1`).

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
Results go to `output/<video id>--<lang>-<hash>/` (one folder per dub) and appear in the website's library. The
website also takes several links at once, YouTube playlists, and video files from this computer.

## Updating
Automatic since 0.5.0: at start (and with the site's «Установить обновление» button) the program installs a newer
`main` from GitHub, keeping `work/`, `output/`, `.env` and `glossary.txt` (`dubber/update.py`, ADR-024); after an
update the page shows "What's new" once (`dubber/changelog.json`). By hand: extract the `main` ZIP over the folder and
double-click `Start Dubber.cmd`. The page footer shows the version.

## Settings (optional, in a `.env` file next to this README)
The website's **Settings** page (gear icon) manages translation: the Claude API key (checked, then saved to `.env`;
only its last 4 characters are ever shown), the model, Claude on/off, and a glossary (`glossary.txt`, one
"term = translation" per line, followed by Claude). Both files are git-ignored.

| Variable | Default | Meaning |
|---|---|---|
| `DUBBER_WHISPER_MODEL` | `small` | `tiny`/`base` faster; `large-v3-turbo` more accurate on French/Hebrew but ~1.5× slower and it skipped English lines in tests (RESEARCH "Session 3") |
| `DUBBER_VOICE` | `ru-RU-DmitryNeural` | or `ru-RU-SvetlanaNeural` |
| `DUBBER_TRANSLATOR` | `auto` | `auto` = Claude if a key is set, else free Google; `google` (free only), `claude`, `offline` (NLLB on this PC). Fallback chain: Claude → Google → offline |
| `ANTHROPIC_API_KEY` | – | enables Claude translation (paid, ~$0.09 per 10 min of speech on Opus 5.5) — normally entered on the website's **Settings** page, which saves it here |
| `DUBBER_CLAUDE_MODEL` | `claude-opus-5-5` | `claude-opus-5-5`, `claude-sonnet-5-5` or `claude-haiku-5-5` (also on the Settings page) |
| `DUBBER_COOKIES` | – | path to a `cookies.txt` exported from your browser, if YouTube says "confirm you're not a bot" |
| `DUBBER_LANG` | `ru` | default dub language (`ru en he uk es fr de it pt ar zh ja`) |
| `DUBBER_KEEP_BACKGROUND` | `1` | `0` = only the dubbed voice, without the original sound underneath (also a switch on the website) |
| `DUBBER_REMOVE_VOICE` | `0` | `1` = keep music and sounds under the dub but remove the speaker's voice (Demucs, ≈ +5 min per 10 min of video on 4 cores; also a switch on the website, CLI `--remove-voice`) |
| `DUBBER_MUSIC_VOLUME` | `0.7` | loudness of that voice-free background (lowered further while the dub speaks) |
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
