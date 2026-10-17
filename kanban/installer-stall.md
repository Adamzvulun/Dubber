---
id: 16
status: doing
priority: High
blocked_by: []
tags: [install, windows, bug]
---

# Installer seems stuck after "Obtaining file:///…"

Adam (2026-10-18): the installer window stays on pip's "Obtaining file:///…" line.

## Narrative
- 2026-10-18: Not reproducible in the sandbox (step ~3 s). Removed pip's silent build-isolation step (setuptools in
  `.venv`, `--no-build-isolation`), added `install.log` and a "can take 10–15 min" note (v0.3.1). Waiting for Adam's
  re-run; if it stalls, read `install.log`. (by @claude)
