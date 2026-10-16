---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
metadata:
  author: vercel
  version: "1.0.0"
  argument-hint: <file-or-pattern>
---

# Web Interface Guidelines

Review files for compliance with Web Interface Guidelines.

## How It Works

1. Read the guidelines (`guidelines.md`, below)
2. Read the specified files (or prompt user for files/pattern)
3. Check against all rules in the fetched guidelines
4. Output findings in the terse `file:line` format

## Guidelines Source

Use the vendored copy next to this file: `guidelines.md` (fetched 2026-10-16 from
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md, MIT, Vercel).
It works without network access. If network is available, you may refresh it from that URL first.
It contains all the rules and the output format instructions.

> Vendored into Dubber from https://github.com/vercel-labs/agent-skills (skills/web-design-guidelines).
> Dubber note: the UI is plain HTML/CSS/JS in `dubber/web/`; design system in `docs/DESIGN.md`.

## Usage

When a user provides a file or pattern argument:
1. Read `guidelines.md` (see above)
2. Read the specified files
3. Apply all rules from the fetched guidelines
4. Output findings using the format specified in the guidelines

If no files specified, ask the user which files to review.
