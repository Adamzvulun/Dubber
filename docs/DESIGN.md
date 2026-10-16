# Design — Dubber website

_Last updated: 2026-10-16_

## Brief
A modern, professional personal tool. The user is a Russian-speaking professional who learns from foreign videos
(any spoken language; the dub defaults to Russian, 12 dub languages). The interface is Russian or English (RU/EN switch).
He is not a beginner with computers; the site should feel like a current, well-made product, not a simplified kiosk.
Primary jobs: (1) paste a link and get a dub, (2) watch and study dubbed videos, (3) download the files.

## Concept: a dubbing studio for learning
The memorable element is the **watch page**: the dubbed video next to a live, bilingual transcript.
The current line is highlighted as the video plays, every line shows the translation with the original under it
(right-to-left languages are right-aligned, original included),
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
| `--surface-2` | `#EEF0F5` | `#19233A` | segmented tracks, select, hover |
| `--accent-soft` | `#E6ECFF` | `#1B2A55` | current transcript line |
| `--danger` | `#C5303B` | `#FF6B75` | errors, delete |

Type: **Onest** (UI and body; a modern grotesque with first-class Cyrillic) and **Unbounded** (wordmark and the
main headline only). Scale 13 (step labels, badges) / 14 / 15 (meta, options) / 16 / 17 (body) / 20 / 24 (watch
title) / 28 / 30–46 (fluid hero) px; tabular numbers for times. Radius by hierarchy: controls 12 px, cards and media
14–16 px, the composer 20 px (the one hero surface), pills 999 px. Shadow: the composer only (the page's main tool).

## Layout
```
Header:  Дубляж (wordmark)                  Новое видео   Библиотека   [RU|EN]
Home:    H1 «Любое видео — на вашем языке» + one sentence
         [ link field ...................................... ][ Озвучить ]
         Язык озвучки [select: 12 languages, "Иврит — עברית"]   Голос [ Мужской | Женский ]
         (switch) Оригинальный звук фоном
         Job cards: running first, then the queue (compact, "Отменить" only), then finished.
           Running: status + lamp, elapsed time, bar, 6-step stepper, note, «Отменить».
           Error: red status with "!" badge, message in ink, «Попробовать снова» / «Скрыть».
         Library grid: 16:9 thumbnails, duration badge, title, dub language · date
Watch:   ‹ Назад в библиотеку
         [ video (2/3) ............ ][ transcript panel (1/3), "Показывать оригинал" ]
         title ................................ Удалить (quiet)
         meta: duration · language · voice · date
         Скачать: [Видео (.mp4)] [Субтитры (.srt)] [Текст перевода (.txt)] [Текст с оригиналом (.txt)]
Mobile:  single column; transcript below the video; header shows the logo mark only; selects full width.
```
Left-aligned text throughout; content max width 1120 px.

## Rules
- Sentence case everywhere; no all-caps labels, no decorative eyebrows, no arrows appended to buttons.
- Buttons say what happens: «Озвучить», «Отменить», «Удалить»; downloads are grouped under a «Скачать» label and
  named by what you get (format in brackets).
- Every UI string lives in `dubber/web/i18n.js` (RU + EN); server messages come as {ru, en}.
- Job cards are patched in place while polling (focus never jumps); stage changes are announced via a polite live
  region; the transcript is one tab stop (arrow keys move between lines).
- Errors say what went wrong and what to do, in the interface's voice.
- Visible keyboard focus, `prefers-reduced-motion` respected, automatic dark mode, works at 360 px width.
