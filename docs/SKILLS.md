# Claude skills used in this project

Skills live in `.claude/skills/<name>/` and load automatically in every Claude Code session opened in this repo.
Third-party skills were reviewed line-by-line before installing (see ADR-005). Update this table whenever a skill is added, updated or removed.

## Installed third-party skills
| Skill | Purpose for Dubber | Source (commit) | License | Notes |
|---|---|---|---|---|
| `brainstorming` | Clarify ideas/requirements before building | [obra/superpowers](https://github.com/obra/superpowers) `bb92a77` | MIT | Optional "visual companion" runs a local web server; it loads a logo from primeradiant.com |
| `writing-plans` | Turn a design into a step-by-step plan | obra/superpowers `bb92a77` | MIT | |
| `executing-plans` | Execute plans task by task with review points | obra/superpowers `bb92a77` | MIT | Its scripts call `subagent-driven-development` |
| `subagent-driven-development` | Dependency of `executing-plans` | obra/superpowers `bb92a77` | MIT | |
| `test-driven-development` | Red → green → refactor | obra/superpowers `bb92a77` | MIT | |
| `systematic-debugging` | Root-cause debugging | obra/superpowers `bb92a77` | MIT | |
| `verification-before-completion` | Prove it works before saying "done" | obra/superpowers `bb92a77` | MIT | |
| `frontend-design` | Design quality for the web UI | [anthropics/skills](https://github.com/anthropics/skills) `dbd4588` | Apache-2.0 | |
| `webapp-testing` | Playwright testing/screenshots of the local UI | anthropics/skills `dbd4588` | Apache-2.0 | |
| `youtube-downloader` | yt-dlp troubleshooting (403, nsig, PO tokens, cookies) | [daymade/claude-code-skills](https://github.com/daymade/claude-code-skills) `4ff168c` | MIT | **`scripts/download_video.py` removed** — it auto-installs pip packages from a third-party mirror without asking |
| `kanban-ai` | Project management: Markdown kanban board in `kanban/` | [mattjoyce/kanban-skill](https://github.com/mattjoyce/kanban-skill) `b86a6ec` | Apache-2.0 | |
| `handoff` | Documentation: hand-off notes between sessions | [mattpocock/skills](https://github.com/mattpocock/skills) `49dd158` | MIT | Invoked manually (`/handoff`) |

## Project skills (written for Dubber)
| Skill | Purpose |
|---|---|
| `dubber-pipeline` | How the pipeline works; how to run, debug and extend each stage |
| `dubber-docs` | The "keep docs updated after every change" checklist |
| `ffmpeg-dubbing` | The ffmpeg recipes we use (extract audio, atempo, ducking, mux, subtitles) |

## Built-in Claude Code skills we use
`session-start-hook` (cloud-session setup), `code-review`, `security-review`, `simplify`, `run`, `skill-creator`.

## Considered but not installed
| Skill | Why not |
|---|---|
| [donghaozhang/ffmpeg-claude-skill](https://github.com/donghaozhang/ffmpeg-claude-skill) | No license → can't redistribute. Replaced by our own `ffmpeg-dubbing` skill. |
| [kwindla/skill-caption-clip](https://github.com/kwindla/skill-caption-clip) | No license; uses paid Deepgram. Ideas (SRT generation, burn-in) used as reference. |
| [bradautomates/claude-video](https://github.com/bradautomates/claude-video) `/watch` | For *Claude* watching videos, not for producing dubs. Reference for yt-dlp + Whisper fallback. |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) PM skills | Jira/Confluence oriented; we use a repo-local kanban instead. |
