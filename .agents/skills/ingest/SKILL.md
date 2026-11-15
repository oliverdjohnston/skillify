---
name: ingest
description: Transcribe every video a creator has posted on TikTok, YouTube and Instagram, merge cross-posts, and extract structured notes from each one. Use when the user wants to process or update a creator's whole account, before turning it into a skill.
---

# Ingest a creator

Two stages, both resumable: rerunning only does what is missing.

1. **Transcripts** (a Python command, no model calls).
2. **Notes** (you, the agent): structured extraction from each unique video.

If `creators/<slug>/profile.json` doesn't exist, set it up with the `creator` skill first.

## Stage 1: transcripts

Ask how much to process (defaults in bold):
- **everything**, the newest N per platform (`--limit N`; on YouTube it is N Shorts plus N
  long-form), or only videos since a date (`--since YYYY-MM-DD`)
- **all platforms in the profile**, or some (`--platform tiktok --platform youtube`)

```bash
creator-skill ingest <slug> [--limit N] [--since YYYY-MM-DD] [--platform NAME]
```

- It's slow on purpose (polite pauses between videos): roughly 5–10 seconds per video with
  captions, longer when Whisper has to transcribe. For more than about 50 videos, run it in the
  background or ask the user to run it in their own terminal. If it's interrupted, rerun the
  same command.
- Each video prints `caption` (the platform's own captions) or `whisper` (local transcription).
- **"<platform> is refusing requests"**: progress is saved. Wait (an hour is usually enough) and
  rerun, or rerun with `--cookies-from-browser firefox` to use the user's own logged-in session.
  Never use proxies, rotating user agents or anything else that dodges a platform's limits.
- Videos that fail 3 times are skipped from then on; `creators/<slug>/state.json` lists why.

Cross-posts (the same clip on several platforms) are merged into one entry in `index.jsonl`
that lists every URL.

## Stage 2: notes

```bash
creator-skill notes-todo <slug>
```

This prints `{"remaining": N, "batches": [[key, ...], ...]}`: unique videos with no complete
note yet, packed so each batch is about 15k transcript words. Videos under 20 words are skipped.

For each batch, give this task to a sub-agent if you can run them, at most 4 in parallel. If you
can't, work through the batches yourself one at a time.

> Read `.agents/skills/ingest/note-template.md` and follow it exactly. For each key in
> `<batch>`, read `creators/<slug>/transcripts/<key>.md` and write
> `creators/<slug>/notes/<key>.md`. Existing topic tags (reuse them where they fit):
> `<output of: creator-skill topics <slug>>`. Read nothing else. Reply only with the keys you
> wrote and any you skipped, with the reason.

When a round finishes, run `notes-todo` again and repeat until `remaining` is 0. A note without
its `## Claims` section counts as unfinished and is redone.

Don't read the transcripts yourself when sub-agents do the work. That keeps a 300-video account
within your context.

## Report

```bash
creator-skill stats <slug>
```

Tell the user:
- the number of videos per platform and how many used captions vs Whisper
- cross-posts merged, and videos with no speech or too short
- notes written, and how many were promo or sponsored
- the date range covered

Point them to the `skillify` skill next.
