# How we work (git)

- **`main` is the stable line.** It always passes CI (`ruff check .` + `pytest`) and is what the PCs run: since
  0.5.0 they **update themselves from `main`** at start (and with the site's «Обновить» button, ADR-024). Merging is
  shipping — a merged change reaches the users' PCs on their next start. Nobody commits to `main` directly. Every release bumps the version and adds its
  changes to `dubber/changelog.json` (shown to the user once after the update).
- **A new branch only for a new feature** (Adam, 2026-10-18), created from the latest `main`: `feat/<short-name>`.
  Fixes, follow-ups and docs for the work in progress go on **that same branch** (or the Claude session's
  `claude/...` branch) — not a new branch per fix. When its PR is merged and more fixes come, continue on the same
  branch name, restarted from the latest `main`.
- **Small commits with clear messages**: an imperative summary line (≤ 72 chars), then why — not just what.
  Run `.venv/bin/ruff check . && .venv/bin/pytest` before every commit.
- **Pull request into `main`** for every branch. Fill in the template (summary, how it was verified, docs updated).
  CI must be green. **Adam reviews and merges** ("Create a merge commit"); then the branch is deleted.
- **Docs travel with the code**: the same PR updates `docs/` and `kanban/` (see `.claude/skills/dubber-docs`).
- **Never commit** cookies, API keys, `.env`, `work/`, `output/`, or videos/frames of third-party videos.
- **Sharing files with Claude**: put them in `dev-uploads/` (see its README); they are deleted once read.
