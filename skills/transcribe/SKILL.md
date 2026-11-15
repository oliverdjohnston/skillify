---
name: transcribe
description: Transcribe specific TikTok, YouTube or Instagram video URLs without processing a whole account. Use when the user pastes one or more video links and wants the transcript or a quick breakdown. Usage: transcribe <video URL> [more URLs] [for <slug>].
---

# Transcribe specific videos

## Before you start

Find the `creator-skill` command and use it for every command below:
1. Inside the skillify repo: `.venv/bin/creator-skill` (Windows: `.venv\Scripts\creator-skill.exe`).
2. Otherwise `creator-skill` on the PATH, or `~/.local/bin/creator-skill`.
3. Neither works: install it with the `start` skill (one command), then come back.

Creator data lives in `creators/` under the current folder.

## Usage

The arguments are the video URLs. `for <slug>` (or naming an existing creator) adds them to that
creator instead of `creators/adhoc/`.

```bash
creator-skill transcribe <url> [<url> ...]                 # saved under creators/adhoc/
creator-skill transcribe <url> --creator <slug>            # add to an existing creator
```

- Short links (`vm.tiktok.com`, `youtu.be`) work.
- Instagram Reels usually need `--cookies-from-browser firefox` (or chrome/safari).
- Platform captions are used when they exist; otherwise the audio goes through local Whisper
  (`--model small` by default; `tiny` is fastest, `medium`/`large` are most accurate).

Transcripts land in `creators/<slug>/transcripts/<platform>_<id>.md`: frontmatter metadata
(URL, date, views, `source: caption|whisper`) followed by the text.

Then read each transcript and give the user what they asked for. If they just want a breakdown,
extract it with `note-template.md` from the `ingest` skill's folder, saved to `creators/<slug>/notes/`. That
way the video counts if they later run `skillify` on that creator.
