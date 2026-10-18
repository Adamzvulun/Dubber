---
id: 22
status: done
priority: High
blocked_by: []
tags: [qa, update, web]
---

# Full QA pass after self-update (v0.5.1)

Adam (2026-10-18): run the QA agents again over everything; trim personal details from the docs.

## Narrative
- 2026-10-18: Three agents (guideline audit, hands-on tester, code review). Fixed: updater failure modes (version
  file last, deps stamp, locked files, path checks, one update at a time), stuck update banner, dub labels, delete
  text, footer/focus/copy. Details in PROGRESS session 4c. (by @claude)
