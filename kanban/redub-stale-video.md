---
id: 12
status: done
priority: High
blocked_by: []
tags: [bug, web]
---

# Re-dub in another language played the old dub

Russian dub, then Hebrew dub of the same video: watch page said Hebrew / Hila, video spoke Russian.

## Narrative
- 2026-10-17: Cause: same URL `/files/<id>/dubbed.mp4`, no cache headers → Chrome reused its cached copy. Fix:
  versioned video URL + `Cache-Control: no-cache` on `/files/`. Reproduced and verified in Chromium. (by @claude)
