# CLAUDE.md — working rules for Dubber

> **Start here: [`docs/STATUS.md`](docs/STATUS.md)** — current state, what's verified, next steps, and sandbox gotchas.

Dubber turns a YouTube video in **any spoken language** (also mixed, e.g. English + French) into a **dubbed** MP4 in one
of 12 languages (**Russian by default**) + subtitles + transcripts, with a steady pace that follows the speaker.
End user: a Russian-speaking professional (not a developer) who learns from foreign videos, running it on his own
Windows PC. The website (RU/EN interface, cancel button) must look like a modern, professional product — `docs/DESIGN.md`.

## Golden rules
1. **The repo is the source of truth.** Every plan, decision and progress note lives in `docs/` and `kanban/`.
   After *any* meaningful change, follow the `dubber-docs` skill: update `docs/PROGRESS.md`,
   tick `docs/PLAN.md`, move/append `kanban/` cards, add an ADR in `docs/DECISIONS.md` when a choice was made.
2. **Work method** (installed skills in `.claude/skills/`):
   `brainstorming` → `writing-plans` → `executing-plans` / `test-driven-development`,
   `systematic-debugging` on bugs, `verification-before-completion` before claiming done.
3. **Never claim it works without running it.** `ruff check . && pytest` must pass before each commit.
4. User-facing text (UI, `docs/README.ru.md`) is in **Russian**; code, comments and dev docs in English.
5. Free tools by default; paid services only behind an opt-in env var.

## Commands
```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # setup (needs ffmpeg on PATH)
.venv/bin/ruff check .                                         # lint
.venv/bin/pytest                                               # tests (no network needed)
.venv/bin/python -m dubber.cli <youtube-url-or-local-file>     # run pipeline
.venv/bin/python -m dubber.app                                 # the website on http://127.0.0.1:7860
.venv/bin/python tools/stub_server.py /tmp/stub 7871           # website with a stand-in pipeline (UI work, no network)
.venv/bin/python tools/qa_languages.py /tmp/qa                 # real dubs of 2 multilingual clips × 12 languages
```

## Layout
- `dubber/` — pipeline stages (`download`, `transcribe`, `translate`, `tts`, `align`, `separate` (optional voice
  removal), `mux`, `subtitles`), orchestrated by
  `pipeline.py`; `languages.py` (the 12 dub languages: voices, codes), `timing.py` (pace planner), `segments.py`
  (lines from word timings), `hub.py` (model downloads), `cli.py`, `app.py` (FastAPI server + JSON API, jobs, cancel,
  settings: Claude key/model/glossary saved to `.env` + `glossary.txt`), `config.py` (settings, `save_env`).
- `dubber/web/` — the website front-end (plain HTML/CSS/JS, no build step): `index.html`, `styles.css`, `app.js`,
  `i18n.js` (every UI string in RU + EN — never hard-code text elsewhere).
- `tools/` — developer tools (not shipped): `stub_server.py`, `qa_languages.py`, `qa_hebrew_voice.py` (see
  docs/STATUS.md "How to test").
- `tests/` — unit tests per stage; network stages are mocked.
- `docs/` — STATUS (start here), PLAN, RESEARCH, DECISIONS, DESIGN, PROGRESS, SKILLS, README.ru.
- `kanban/` — task cards (see `kanban-ai` skill).
- `work/<id>/` — per-video cache (git-ignored). `output/<id>/` — finished video + subtitles + transcripts + `meta.json`
  + `thumbnail.jpg` + `segments.json`; the website library reads this folder (git-ignored).

## Gotchas (details in docs/STATUS.md)
- Cloud sandbox: YouTube and Google Translate block datacenter IPs (use fresh cookies via `DUBBER_COOKIES`, kept
  outside the repo; translation falls back to the offline NLLB model, 1.4 GB on first use). Headless Chromium can't
  play H.264. Test media = local files or `tools/qa_languages.py` clips.
- Never commit cookies, API keys, `.env`, `glossary.txt`, `work/`, `output/`, or frames/dubs of third-party videos.
- Tests that save settings must use a temp `env_file`/`glossary_file` (see `tests/test_app.py`), never the real `.env`.
- `pkill -f dubber.app` kills your own shell — kill by PID (see STATUS).
- Every release: bump `__version__` (`dubber/__init__.py`) and `pyproject.toml`; the page links its files by version,
  and the PCs update themselves only when `main` has a **higher** version (`dubber/update.py`, ADR-024).
  Merging into `main` ships to the PCs on their next start.

## Git
Full rules: `CONTRIBUTING.md`. In short: **`main` is the stable line** — start from the latest `main`; **a new branch
only for a new feature** (`feat/…`) — fixes and follow-ups to the current work stay on the same branch (or the
session's `claude/…` branch), never one branch per fix (Adam, 2026-10-18); never commit to `main`,
open a PR into `main` (template in `.github/`), CI (`ruff` + `pytest`, `.github/workflows/ci.yml`) must be green,
and **Adam reviews and merges**. Files Adam shares arrive on `uploads/…` branches in `dev-uploads/` (see its README);
delete them in your next PR after reading. The old `claude/bold-davinci-qfv627` branch is outdated — ignore it.
