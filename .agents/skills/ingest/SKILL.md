---
name: ingest
description: Transcribe every video a creator has posted on TikTok, YouTube and Instagram, merge cross-posts, and extract structured notes from each one. Use when the user wants to process or update a creator's whole account, before turning it into a skill. Usage: ingest <slug> [all | N | since YYYY-MM-DD] [tiktok|youtube|instagram] [notes-only].
---

# Ingest a creator

Two stages, both resumable: rerunning only does what is missing.

1. **Transcripts** (a Python command, no model calls).
2. **Notes** (you, the agent): structured extraction from each unique video.

## Before you start

If `.venv/bin/creator-skill` doesn't exist (Windows: `.venv\Scripts\creator-skill.exe`), do the
`start` skill's setup first, then come back.

## Read the arguments

| The user wrote | Means |
|---|---|
| `ana` | creator slug. If none is given and only one creator exists, use it; if several, ask which |
| a profile URL or `@handle` instead of a slug | not set up yet: run the `creator` skill first, then continue here |
| `all` / `everything` | no limit |
| `20` | `--limit 20`: the newest 20 per platform (on YouTube, 20 Shorts plus 20 long-form) |
| `since 2026-01-01` | `--since 2026-01-01` |
| `tiktok`, `youtube`, `instagram` | `--platform <name>` (repeatable); default is every platform in the profile |
| `notes-only` | skip stage 1 |

If the amount isn't given, ask once: **everything**, or the newest N first? Don't ask anything
else that has a default.

## Stage 1: transcripts

```bash
.venv/bin/creator-skill ingest <slug> [--limit N] [--since YYYY-MM-DD] [--platform NAME]
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
.venv/bin/creator-skill notes-todo <slug>
```

This prints `{"remaining": N, "batches": [[key, ...], ...]}`: unique videos with no complete
note yet, packed so each batch is about 15k transcript words. Videos under 20 words are skipped.

For each batch, give this task to a sub-agent if you can run them, at most 4 in parallel. If you
can't, work through the batches yourself one at a time.

> Read `.agents/skills/ingest/note-template.md` and follow it exactly. For each key in
> `<batch>`, read `creators/<slug>/transcripts/<key>.md` and write
> `creators/<slug>/notes/<key>.md`. Existing topic tags (reuse them where they fit):
> `<output of: .venv/bin/creator-skill topics <slug>>`. Read nothing else. Reply only with the keys you
> wrote and any you skipped, with the reason.

When a round finishes, run `notes-todo` again and repeat until `remaining` is 0. A note without
its `## Claims` section counts as unfinished and is redone.

Don't read the transcripts yourself when sub-agents do the work. That keeps a 300-video account
within your context.

## Report

```bash
.venv/bin/creator-skill stats <slug>
```

Tell the user:
- the number of videos per platform and how many used captions vs Whisper
- cross-posts merged, and videos with no speech or too short
- notes written, how many were promo (down-weighted) and how many had a sponsor read
- the date range covered

Point them to the `skillify` skill next.
