---
name: creator
description: Add, edit or list creator profiles that map one person to their TikTok, YouTube and Instagram accounts. Use when the user wants to add a creator, change their handles, or see which creators are set up.
---

# Creator profiles

A profile is `creators/<slug>/profile.json`:

```json
{"name": "Ana Example", "lang": "en", "tiktok": "@ana", "youtube": "@ana", "instagram": "ana"}
```

- `slug`: lowercase-hyphenated folder name, e.g. `ana-example`.
- `lang`: the language they speak (2 letters). It picks the right captions, and Whisper output
  in another language is treated as music or noise.
- Any platform can be left out. Handles or full profile URLs both work.

## Add or edit

```bash
creator-skill creator add <slug> --name "Ana Example" --tiktok @ana --youtube @ana --instagram ana
```

Running `add` again on an existing slug only changes the fields you pass.

Then check that the handles resolve, without downloading anything:

```bash
creator-skill ingest <slug> --dry-run --limit 1
```

Each platform should list one video. If a platform lists nothing or errors, the handle is wrong.

## Instagram

yt-dlp can't list Instagram profiles at the moment, so Reels come from a URL list. Ask the user
to paste Reel links (from the profile page in a browser) into `creators/<slug>/instagram_urls.txt`,
one per line. Most Reels are cross-posts of TikToks or Shorts that get merged anyway, so a handful
of Instagram-only Reels is enough. Reels usually need the user's browser cookies, so ingest with
`--cookies-from-browser firefox` (or chrome/safari); it uses their own logged-in session.

## List

```bash
creator-skill creator list
```

An old `accounts.json` from earlier versions is migrated into profiles automatically.
