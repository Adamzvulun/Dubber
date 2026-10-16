# CLAUDE.md — working rules for Dubber

Dubber turns an English YouTube video into a **Russian-dubbed** MP4 + Russian subtitles + transcript.
End user: a Russian-speaking, non-technical person running it on his own PC (Windows likely).

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
.venv/bin/python -m dubber.app                                 # Russian web UI on http://127.0.0.1:7860
```

## Layout
- `dubber/` — pipeline stages (`download`, `transcribe`, `translate`, `tts`, `align`, `mux`, `subtitles`), orchestrated by `pipeline.py`; `cli.py`, `app.py`.
- `tests/` — unit tests per stage; network stages are mocked.
- `docs/` — PLAN, RESEARCH, DECISIONS, PROGRESS, SKILLS, README.ru.
- `kanban/` — task cards (see `kanban-ai` skill).
- `work/` — per-video cache (git-ignored). `output/` — finished files (git-ignored).

## Git
Develop on the branch given in the session; commit with clear messages; push with `git push -u origin <branch>`.
