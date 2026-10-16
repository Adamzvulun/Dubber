---
name: dubber-docs
description: Checklist for keeping Dubber's project documentation current. Use after finishing any task, fix, decision or session in this repo, and before every commit/push.
---

# Keep the docs true

The repository is the project's memory. Before committing, walk this list:

0. **`docs/STATUS.md`** — the handoff page: keep "what works / not verified / next steps / gotchas" true.
1. **`docs/PROGRESS.md`** — add/extend today's entry at the top: what was done, what was learned, what's blocked.
2. **`docs/PLAN.md`** — tick finished items, add newly discovered work, update "Open questions" and the date.
3. **`kanban/`** — move cards (`status:`), append a `## Narrative` note with the *why* (see `kanban-ai` skill).
   New work → new card.
4. **`docs/DECISIONS.md`** — a new ADR whenever a tool/approach was chosen or rejected.
5. **`docs/SKILLS.md`** — when a skill is added/removed/updated (source, commit, license, notes).
6. **`docs/RESEARCH.md`** — new findings about tools, with source links.
7. **User-facing docs** — `README.md` (dev, English) and `docs/README.ru.md` (father, Russian) if behaviour,
   install steps or the UI changed.
8. **`CLAUDE.md`** — if commands, layout or working rules changed.

Keep entries short and factual. Never claim something works unless it was run (see `verification-before-completion`).
