---
id: 9
status: done
priority: High
blocked_by: []
tags: [m6, languages, i18n, cancel, qa]
---

# Cancel button, any-language dubbing, RU/EN interface, agent QA

Adam (2026-10-16): add a cancel button; the last video had French in it — translate any language, into other
languages too; find a QA skill and let an agent go over the whole UX/UI. Plan: `docs/PLAN.md` M6; ADR-014, ADR-015.

## Narrative
- 2026-10-16: Cancel (API + UI) done. Language-run transcription (fixes dropped French/English passages), 12 dub
  languages, language-coded outputs, RU/EN interface done; verified with a real mixed EN/FR clip dubbed into Hebrew
  (Google blocked in the sandbox → Hebrew text supplied by hand for that run). Installed `web-design-guidelines`;
  two QA agents running. (by @claude)
- 2026-10-16: QA agents reported ~40 findings; all real ones fixed and re-verified in Chromium (focus, skip link,
  360 px, dark mode, transcript keys, job order). Remaining: real non-Russian dub on Adam's PC (Google). (by @claude)
