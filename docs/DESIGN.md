# Design — Dubber website

_Last updated: 2026-10-16_

## Brief
A modern, professional personal tool. The user is a Russian-speaking professional who learns from English videos.
He is not a beginner with computers; the site should feel like a current, well-made product, not a simplified kiosk.
Primary jobs: (1) paste a link and get a dub, (2) watch and study dubbed videos, (3) download the files.

## Concept: a dubbing studio for learning
The memorable element is the **watch page**: the dubbed video next to a live, bilingual transcript.
The current line is highlighted as the video plays, every line shows Russian with the English original under it,
and clicking a line jumps the video there. Everything else stays quiet and disciplined around it.

The one deliberate motion moment: a red "live" light (like a studio's on-air lamp) pulses while a dub is in progress.

## Tokens
| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F4F5F8` | `#0B111C` | page |
| `--surface` | `#FFFFFF` | `#121A28` | cards, panels |
| `--ink` | `#0D1B2E` | `#E8ECF3` | text |
| `--ink-2` | `#4A5568` | `#9AA6B8` | secondary text |
| `--line` | `#E3E6EC` | `#233047` | borders |
| `--accent` | `#2F5BFF` | `#6E8BFF` | primary actions, focus, progress |
| `--live` | `#E5484D` | `#FF6369` | "dubbing now" lamp only |
| `--ok` | `#1F9D6B` | `#3CCB8F` | finished steps |

Type: **Onest** (UI and body; a modern grotesque with first-class Cyrillic) and **Unbounded** (wordmark and the
main headline only). Scale 14 / 16 / 17 (body) / 20 / 28 / 44 px; tabular numbers for times.
Radius by hierarchy: controls 12 px, cards 16 px, pills 999 px. Shadows only on floating elements.

## Layout
```
Header:  Дубляж (wordmark)                         Новое видео   Библиотека
Home:    H1 + one sentence
         [ link field ...................................... ][ Озвучить ]
         Voice: [ Дмитрий | Светлана ]    (switch) Оригинальный звук фоном
         Active job card: 6-step stepper (a real sequence) + bar + elapsed time
         Library grid: 16:9 thumbnails, duration badge, title, date
Watch:   [ video (2/3) ............ ][ transcript panel (1/3) ]
         title, channel, downloads row, delete
Mobile:  single column; transcript below the video.
```
Left-aligned text throughout; content max width 1120 px.

## Rules
- Sentence case everywhere; no all-caps labels, no decorative eyebrows, no arrows appended to buttons.
- Buttons say what happens: «Озвучить», «Скачать видео», «Удалить».
- Errors say what went wrong and what to do, in the interface's voice.
- Visible keyboard focus, `prefers-reduced-motion` respected, automatic dark mode, works at 360 px width.
