# dev-uploads — files for Claude to look at

A drop box for things Adam wants Claude to see (logs, cache files, screenshots) when there are too many to attach in
the chat. Claude reads them, writes what it learned in `docs/` / `kanban/`, and deletes them in its next PR.

## How to upload (in the browser)
1. Open the repository on GitHub, branch `main`, folder `dev-uploads`.
2. **Add file → Upload files**, drag the files in (a whole folder works too).
3. At the bottom choose **"Create a new branch for this commit"**, name it `uploads/<what>` (e.g.
   `uploads/translation-timing`), and press **Propose changes** (you don't need to open the pull request).
4. Tell Claude the branch name in the chat.

## Never upload
Cookies (`cookies.txt`), API keys, the `.env` file, passwords, or videos/audio (large, and third-party content).
The repository is private, but everything uploaded stays in the git history.

## Wanted now: translation / timing got worse (`kanban/translation-timing-regression.md`)
From `work\<video-id>\` of the English+French video (the id is the folder name, same as in `output\`):
- every `segments_*.json` and `segments_*.translator`
- every `timing_*.json`
- `speech_info.json`, `info.json`

From `output\<video-id>\`: `meta.json`, `timing.json`.
Plus a short note (a `.txt` file is fine): one or two moments (minute:second) where the translation or the timing got
worse.
