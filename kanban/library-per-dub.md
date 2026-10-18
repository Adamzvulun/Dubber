---
id: 19
status: done
priority: High
blocked_by: []
tags: [library, bug, web]
---

# Each dub of a video is its own library entry

Adam (2026-10-18): dubbed the same video twice with other settings/language; both entries played the newest dub.

## Narrative
- 2026-10-18: Cause: all dubs of a video shared `output/<video-id>/`. Now one folder per dub
  (`<video-id>--<lang>-<hash>`), same choices replace it (Adam's choice), watch page links the other dubs; old
  folders untouched (ADR-022, v0.4.1). Verified with real pipeline runs + Chromium. (by @claude)
