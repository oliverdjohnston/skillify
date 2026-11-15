---
name: ingest
description: Transcribe every video a creator has posted on TikTok, YouTube and Instagram, merge cross-posts, and extract structured notes from each one. Use when the user wants to process or update a creator's whole account, before turning it into a skill. Usage: ingest <slug> [all | N | since YYYY-MM-DD] [tiktok|youtube|instagram] [notes-only].
---

# Ingest a creator

Two stages, both resumable: rerunning only does what is missing.

1. **Transcripts** (a Python command, no model calls).
2. **Notes** (you, the agent): structured extraction from each unique video.

## Before you start

Use `.venv/bin/creator-skill` inside the skillify repo, otherwise `creator-skill` on the PATH. If
neither exists, set it up with the `start` skill first.

Creator data lives in `creators/` under the current folder.

## Read the arguments

| The user wrote | Means |
|---|---|
| `ana` | creator slug. If none is given and only one creator exists, use it; if several, ask which |
| a profile URL or `@handle` instead of a slug | not set up yet: run the `creator` skill first, then continue here |
| `all` / `everything` | no limit |
| `20` | `--limit 20`: the newest 20 per platform (on YouTube, 20 Shorts plus 20 long-form) |
| `since 2026-01-01` | `--since 2026-01-01` |
| `top 150` | `--most-viewed 150`: only the 150 most-viewed videos per platform |
| `tiktok`, `youtube`, `instagram` | `--platform <name>` (repeatable); default is every platform in the profile |
| `notes-only` | skip stage 1 |

If the amount isn't given, ask once: **everything**, or the newest N first? Don't ask anything
else that has a default.

## Stage 1: transcripts

```bash
creator-skill ingest <slug> [--limit N] [--since YYYY-MM-DD] [--platform NAME]
```

- It first lists the whole profile (a few minutes for a 2,000-video account), then handles 4
  videos at once with a polite pause after each: roughly 1,000 captioned videos
  an hour, slower when Whisper has to transcribe. For more than about 50 videos, run it in the
  background or ask the user to run it in their own terminal. If it's interrupted, rerun the
  same command.
- Each video prints `caption` (the platform's own captions) or `whisper` (local transcription).
- **"<platform> is refusing requests"**: progress is saved; follow the advice it prints. Never use
  proxies, rotating user agents or anything else that dodges a platform's limits.
- **"WARNING: … listing ended early"**: TikTok sometimes stops listing partway. Rerun the same
  command later to pick up the rest.
- Videos that fail 3 times are skipped from then on; `creators/<slug>/state.json` lists why.

Cross-posts (the same clip on several platforms) are merged into one entry in `index.jsonl`
that lists every URL.

## Stage 2: notes

```bash
creator-skill notes-todo <slug>
```

Notes are the expensive step: roughly 100k tokens per batch (about 1,300 per short video). If your agent lets you choose the
sub-agents' model, a smaller one handles short videos about as well, but in testing it caught
only a third of the claims in long interviews, so prefer a capable model for long videos. If the creator has many long videos
(podcasts, streams), say how many batches there are and offer to note only the most-viewed long
ones: `creator-skill notes-todo <slug> --long-top 150` keeps every short video plus the 150
most-viewed videos over 3 minutes.

This prints `{"remaining": N, "batches": [[key, ...], ...]}`: unique videos with no complete
note yet, packed so each batch is at most 75 videos or 30k transcript words. Bigger batches are
much cheaper per note, because each sub-agent's fixed overhead is shared. Videos under 20 words are skipped.

For each batch, give this task to a sub-agent if you can run them, at most 4 in parallel. If you
can't, work through the batches yourself one at a time.

> Read `<absolute path of note-template.md in this skill's folder>` and follow it exactly. For each key in
> `<batch>`, read `creators/<slug>/transcripts/<key>.md` and write
> `creators/<slug>/notes/<key>.md`. Existing topic tags (reuse one where it fits; otherwise make a
> new kebab-case tag; never leave a video with speech untagged):
> `<output of: creator-skill topics <slug>>`. Write each note yourself (scripts only to check
> quotes), and keep any helper files in your own new folder. Read nothing else. Reply only with the keys you
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
- notes written, how many were promo (down-weighted) and how many had a sponsor read
- `quotes_verbatim`: if well under 90%, spot-check a few notes for invented quotes
- the date range covered

Point them to the `skillify` skill next.
