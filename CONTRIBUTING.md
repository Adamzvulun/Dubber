# How we work (git)

- **`main` is the stable line.** It always passes CI (`ruff check .` + `pytest`) and is what Adam installs
  (GitHub → Code → Download ZIP, then `scripts\install_windows.bat`). Nobody commits to `main` directly.
- **One branch per piece of work**, created from the latest `main`:
  `feat/<short-name>` (new feature), `fix/<short-name>` (bug), `chore/<short-name>` (tooling, docs, cleanup).
  Claude Code sessions may also work on their session branch (`claude/...`); the same rules apply.
- **Small commits with clear messages**: an imperative summary line (≤ 72 chars), then why — not just what.
  Run `.venv/bin/ruff check . && .venv/bin/pytest` before every commit.
- **Pull request into `main`** for every branch. Fill in the template (summary, how it was verified, docs updated).
  CI must be green. **Adam reviews and merges** ("Create a merge commit"); then the branch is deleted.
- **Docs travel with the code**: the same PR updates `docs/` and `kanban/` (see `.claude/skills/dubber-docs`).
- **Never commit** cookies, API keys, `.env`, `work/`, `output/`, or videos/frames of third-party videos.
- **Sharing files with Claude**: put them in `dev-uploads/` (see its README); they are deleted once read.
