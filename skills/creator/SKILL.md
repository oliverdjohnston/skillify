---
name: creator
description: 'Add a creator from their TikTok, YouTube or Instagram handles or profile links, check the accounts resolve, then offer to transcribe them and build their skill. Also lists and edits creators. Use when the user gives a creator''s handle or profile URL, or asks to add, change or list creators. Usage: creator <profile URL or @handle> [more URLs] ["Display Name"], creator list, creator edit <slug> ...'
---

# Creator

## Before you start

Use `.venv/bin/understudy` inside the understudy repo, otherwise `understudy` on the PATH. If
neither exists, set it up with the `start` skill first.

Creator data lives in `creators/` under the current folder. No account or sign-in is needed for
public TikTok and YouTube profiles.

## Read the arguments

Everything after the skill name is the input. Work out as much as you can from it, and ask only
for what is genuinely missing:

| The user wrote | Means |
|---|---|
| `https://www.tiktok.com/@ana` | TikTok `@ana` |
| `https://www.youtube.com/@AnaMakes` | YouTube `@AnaMakes` |
| `https://www.instagram.com/ana` | Instagram `ana` (see Instagram below) |
| `@ana` (no platform) | TikTok `@ana`; say you assumed TikTok |
| `"Ana Example"` (quoted text) | display name |
| `list` | list creators |
| `edit <slug> youtube @x` | change one field |

- **slug**: the first handle, lowercase, with anything other than letters or digits turned into
  hyphens (`@Ana.Makes` → `ana-makes`). Reuse an existing slug if this creator is already set up.
- **name**: the quoted text, else the handle without `@`.
- **YouTube tabs**: a handle covers Shorts and long-form. A tab URL (`.../@ana/videos`) covers just
  that tab. Shorts are often copies of the creator's TikToks, so `/videos` saves time if they post
  on both.
- **lang**: `en`, unless the user says otherwise or the creator obviously speaks another
  language. It picks the right captions, and Whisper output in other languages is discarded.

## Add or edit

```bash
understudy creator add <slug> --name "<name>" [--tiktok @x] [--youtube @x] [--instagram x] [--lang en]
understudy ingest <slug> --dry-run --limit 1
```

The dry run lists one video per platform without downloading anything. If a platform lists
nothing or errors, the handle is probably wrong: tell the user and ask for the right one.
Running `add` again on an existing slug only changes the fields you pass.

## Offer the next step

Show what was saved, then ask one question:

> Transcribe <name>'s videos now? **Everything**, or just the **newest N** per platform first
> (e.g. 20, good for a quick test)?

If they say yes, continue straight into the `ingest` skill with that choice. When ingest
finishes, offer the `understudy` skill.

## Instagram

yt-dlp can't list Instagram profiles at the moment, so Reels come from a URL list. Save the
Instagram handle in the profile as usual (ingest only runs platforms the profile names), and ask
the user to paste Reel links into `creators/<slug>/instagram_urls.txt`, one per line. A handful is enough;
most Reels are cross-posts of TikToks or Shorts anyway. Instagram does need a sign-in: ingest
with `--cookies-from-browser firefox` (or chrome/safari) while the user is logged in to Instagram
in that browser. It uses their own session; nothing is stored here.

## List

```bash
understudy creator list
```

An old `accounts.json` from earlier versions is migrated into profiles automatically.
