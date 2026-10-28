---
id: 33
status: done
priority: High
blocked_by: []
tags: [windows, install, subtitles, v0.8.0]
---

# Session 7: flawless Windows 11 install + on-screen subtitles (v0.8.0)

Adam (2026-10-28): "some package was missing" when installing a few days ago — go over the install again, father's
PC is Windows 11; then real-time subtitles on the dubbed video.

## Narrative
- 2026-10-28: Audit: every component has Windows wheels for Python 3.10–3.14; found the Visual C++ runtime gap
  (onnxruntime/ctranslate2 import msvcp140.dll + msvcp140_1.dll, not shipped by Python, preinstalled on the CI image)
  and no fallback without winget. Fixed in `dubber.ps1` + `dubber/deps.py` (ADR-029); new `clean-pc` CI job.
  The CI then reproduced a real install failure on Windows: pip "No matching distribution found for
  onnxruntime>=1.17 (from versions: none)". Root cause: Python 3.15 (Oct 2026) picked by `py -3`, no onnxruntime
  build for it. Launchers now use 3.10–3.14 only and rebuild a venv from a too-new Python (ADR-029). (by @claude)
- 2026-10-28: Subtitles: two switches under the player (Adam's choice), browser-drawn text track (ADR-030); checked
  in Chromium (RU/EN, 1280/360 px, dark, Hebrew RTL + English, CC-menu sync). (by @claude)
- 2026-10-28: Merged as PR #13 (v0.8.0). Real Windows 11 install still to be confirmed by Adam. (by @claude)
