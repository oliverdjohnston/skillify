# AGENTS.md

## Ownership

This codebase belongs to the agents who work on it. Its purpose and its design are yours to own,
and you are the one who keeps building it. Treat it like your own project: keep it small and
readable, leave it better than you found it, and record decisions here so the next agent (very
likely you, without memory of this session) can carry on.

## What it is for

**Understudy** (the `creator-skill` tool plus its agent skills) turns a creator's whole output
across TikTok, YouTube (Shorts and long-form) and Instagram into one high-quality agent skill,
built from what they actually say. The test of success: someone using the generated skill gets that creator's real methods and voice, every
point traceable to a video, with no generic padding.

It is agent-agnostic. Skills use the open SKILL.md format (frontmatter `name` + `description`,
optional `references/`). Never depend on one vendor's tools in a skill: write "if you can run
sub-agents…, otherwise…".

## How it works

```
creator-skill ingest <slug>        Python: list → captions (or Whisper) → transcripts → dedupe → index.jsonl
notes (agent, ingest skill)        agent: one structured note per unique video
understudy (agent, understudy skill) agent: map-reduce notes → skill/<name>/SKILL.md + references/
```

All data for a creator lives in `creators/<slug>/` (git-ignored, because it is other people's
content):

```
profile.json            {"name", "lang", "tiktok", "youtube", "instagram"}
instagram_urls.txt      Reel URLs (yt-dlp can't list Instagram profiles)
state.json              failures (a video is skipped after 3 tries) and listing counts per handle
transcripts/<platform>_<id>.md   JSON-valued frontmatter + text; the file existing = done
index.jsonl             one line per unique video (cross-posts merged), rebuilt from transcripts
notes/<key>.md          agent-written, see skills/ingest/note-template.md
skill/<name>/           generated skill before installation
```

Code in `src/creator_skill/` (one job per module):

| Module | Job |
|---|---|
| `ytdlp.py` | the **only** yt-dlp code: listing, metadata, caption choice/cleaning, audio, `Blocked`, `window()` for --since/--limit |
| `providers/` | one module per platform with `NAME`, `DOMAINS`, `DELAY`, `list_videos`, `fetch_captions`, `download_audio`. Ingest runs a platform only when the profile has a handle for it; citation checks and URL routing derive from `PROVIDERS`. To add X: one module plus one entry in `PROVIDERS` |
| `transcribe.py` | mlx-whisper on Apple Silicon if installed, else faster-whisper |
| `ingest.py` | profiles, resumable ingest, ad hoc URLs |
| `dedupe.py` | cross-post merging, `index.jsonl` |
| `notes.py` | read-only helpers for the agent steps: `notes-todo`, `topics`, `sources`, `stats`, `check` |
| `models.py` | `Video`, transcript read/write, atomic writes |
| `cli.py`, `doctor.py` | the `creator-skill` command and environment check |

Project skills live in `skills/`, the layout `npx skills add oliverdjohnston/understudy` installs
from. `.agents/skills` (Codex) and `.claude/skills` (Claude Code) are symlinks to it: `start`,
`creator`, `ingest`, `transcribe`, `understudy`.

## Decisions (and why)

- **Captions first, Whisper second.** Platform captions are free and usually better. Never use
  a machine-translated track: on YouTube use a manual track in the creator's language or the
  `*-orig` auto track; on TikTok use the single track, or the one in the creator's language.
- **YouTube auto-dubbed videos** have one `*-orig` track per dub language: pick the one in the
  profile's `lang`, and any other only when it is the sole track.
- **TikTok caption cues are out of order** in the file: `clean_subtitles` sorts them by start time.
- **Interviews**: notes keep guests' points under `## Guest`, never in Claims; the understudy step ignores them.
- **Whisper output in a language other than the profile's `lang` is dropped** (saved with 0
  words). Whisper invents text on music-only clips.
- **No platform evasion.** No proxies, no user-agent rotation, and no `curl-cffi` impersonation
  by default. Rate limits raise `Blocked`: save progress, tell the user, suggest waiting or
  their own cookies. If yt-dlp can't do something, tell the user and offer options; don't hack
  around it.
- **Instagram is a URL list** because yt-dlp's `instagram:user` extractor is broken. Revisit
  when yt-dlp fixes it.
- **YouTube needs deno + yt-dlp-ejs** (installed with the `yt-dlp[default,deno]` extra) for
  downloads. Captions mostly work without them.
- **Installed skills find the tool themselves**: the repo's `.venv`, else `creator-skill` on the
  PATH, else a one-time `uv tool install "creator-skill[mac] @ git+https://github.com/oliverdjohnston/understudy"`.
  ffmpeg is optional (only mlx-whisper needs it), so uv is the only prerequisite.
- **Notes and synthesis are done by the agent, not an API key.** Python stays deterministic and
  cheap. The agent does the judgement.
- **Faithfulness over helpfulness** in notes and skills. Web research only with `--enrich`, and
  labelled as external.
- **All yt-dlp calls go through `ytdlp._blocking()`**, which turns rate limits and bot checks into
  `Blocked`. Providers use `ytdlp.DownloadError`, never `yt_dlp` directly.
- **Resume by file existence**, with atomic writes. Never add a database.
- **Platforms run in parallel, 4 videos at once each by default** (`--workers`). Each worker has
  its own yt-dlp client (not thread-safe) and keeps its platform's polite pause (`DELAY`);
  Whisper runs one job at a time behind a lock.
- **Each platform is listed in full before any video is processed**: a paused listing lets
  TikTok's cursor expire. TikTok listings still sometimes end early, so `state.json` remembers
  the biggest count per handle and ingest warns when a listing comes back under 90% of it.
- `--limit N` is per platform (per tab on YouTube). `--since` stops after 5 old videos in a row,
  because pinned posts are old. `--most-viewed N` sorts the full listing by views (the listing
  already has them) and keeps the top N per platform.

## Working here

- Setup: `uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev,mac]"`, then
  `.venv/bin/creator-skill doctor`.
- Before every commit: `ruff check . && ruff format --check . && pytest` (unit tests only by
  default). `pytest -m live` hits YouTube once; run it when you touch `ytdlp.py` or providers.
- When you touch the agent skills, run the flow end to end on a small real creator
  (`ingest --limit 3`), then notes, then the understudy step, then `creator-skill check`.
- Keep the code small: standard library first, no speculative options, one test per
  non-trivial branch. A known limitation gets a `# shortcut: <limit>, <when to upgrade>`
  comment.
- yt-dlp breaks often. When a platform stops working, first upgrade yt-dlp
  (`uv pip install -U "yt-dlp[default,deno]"`) and rerun `pytest -m live`.
- Commits: small and logical, with British English messages and no attribution lines.
- Update this file when you make a decision the code can't explain on its own.

## Known gaps

- Instagram hasn't been tested live in this repo yet (it needs real Reel URLs and cookies).
- TikTok caption keys use ISO 639-2 (`eng-US`); `LANG3` in `ytdlp.py` maps only a few languages.
  Extend it when a creator speaks another one.
