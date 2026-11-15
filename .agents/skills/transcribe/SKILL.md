---
name: transcribe
description: Transcribe specific TikTok, YouTube or Instagram video URLs without processing a whole account. Use when the user pastes one or more video links and wants the transcript or a quick breakdown.
---

# Transcribe specific videos

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
extract it with `.agents/skills/ingest/note-template.md`, saved to `creators/<slug>/notes/`. That
way the video counts if they later run `skillify` on that creator.
