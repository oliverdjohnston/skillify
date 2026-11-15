# creator-skill

Turn everything a creator says on TikTok, YouTube (Shorts and long-form) and Instagram into one
agent skill built from their own words: their methods, their voice, or both. Every point in the
skill links back to the videos it came from.

It works with any agent that reads [Agent Skills](https://agentskills.io) (`SKILL.md`), such as
Claude Code and Codex. You don't need an API key. Transcription runs on your machine and your
agent does the reading and writing.

## How it works

1. **Ingest** downloads each video's metadata and transcript. It uses the platform's own
   captions when they exist and local Whisper when they don't, and merges cross-posts (the same
   clip on TikTok, Reels and Shorts).
2. **Notes**: your agent writes structured notes for every unique video: claims, frameworks,
   examples, numbers, tools, hooks and phrasing. Guests' views in interviews are kept apart from
   the creator's.
3. **Skillify**: your agent groups the notes by topic, ranks advice by how often it comes up and
   how well those videos did, takes the newer view when the creator changed their mind, and
   writes a skill folder you can install.

## Install

Into your agent, without cloning (Claude Code, Codex and others that read skills):

```bash
npx skills add oliverdjohnston/skillify
```

Then, in any folder, run `/creator https://www.tiktok.com/@theirhandle`. The first time, the
skill offers to install the `creator-skill` tool with [uv](https://docs.astral.sh/uv/), and
installs uv too if you don't have it. uv also fetches Python, so there's nothing else to set up.

Or clone it, to change the code or use it without an agent:

```bash
git clone https://github.com/oliverdjohnston/skillify.git && cd skillify
uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev,mac]"
.venv/bin/creator-skill doctor      # prints a fix for anything missing
```

No uv? Use `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` (Python 3.11 or newer).

### Supported systems

| System | Whisper backend | Notes |
|---|---|---|
| macOS on Apple Silicon | mlx-whisper | Fastest. Needs the `mac` extra and ffmpeg (`brew install ffmpeg`); without ffmpeg it falls back to faster-whisper |
| macOS on Intel, Linux | faster-whisper | Runs on the CPU |

## Make a skill from a TikTok account

In your agent (in Claude Code, skills are slash commands):

```
/creator https://www.tiktok.com/@theirhandle
```

It saves the creator and checks the account, then offers to transcribe the videos and build the
skill, asking only for what it can't work out. Each skill also takes its options directly:

| Command | Does |
|---|---|
| `/creator <TikTok/YouTube/Instagram URLs> "Name"` | add a creator (one person, several platforms) |
| `/ingest ana 20` · `/ingest ana all` · `/ingest ana since 2026-01-01 tiktok` | transcribe and take notes |
| `/skillify ana both` · `/skillify ana voice --enrich` | build the skill |
| `/transcribe <video URLs>` | one-off videos |

Each skill sets up the Python tool itself if needed, so `/start` is optional.

You don't need an account for public TikTok and YouTube profiles. Instagram, and age-restricted
YouTube videos, use the cookies from a browser where you're logged in:
`--cookies-from-browser firefox`. Private accounts can't be processed.

### Cost and time

Transcripts are free: captions come from the platform and Whisper runs locally. The notes are
where your agent spends tokens, roughly 1,300 per short video or 100k per batch of up to 75
videos. For a large account, `/ingest` tells you how many batches there are first and can limit
notes to the most-viewed long videos. Ingest pauses between videos to stay polite to the platforms,
so a big account takes a while, and it picks up where it stopped if you interrupt it.

### Without an agent

```bash
creator-skill creator add ana --name "Ana Example" --tiktok @ana   # add --youtube @ana etc.
creator-skill ingest ana --dry-run --limit 3                       # check the handle works
creator-skill ingest ana                                           # every video; resumable
```

Then ask your agent to run `/ingest ana notes-only` and `/skillify ana`. Skillify asks whether
you want knowledge, voice or both, which topics to include, and where to install the result:
`~/.claude/skills/` for Claude Code, `~/.agents/skills/` for Codex and other agents that read
it, or a single project.

Useful options for `ingest`:

| Option | Effect |
|---|---|
| `--limit N` | only the newest N per platform (per tab on YouTube: N Shorts + N long-form) |
| `--since 2026-01-01` | skip older videos |
| `--most-viewed N` | only the N most-viewed videos per platform |
| `--platform tiktok` | one platform (repeatable) |
| `--model tiny\|base\|small\|medium\|large` | Whisper size for videos without captions (default `small`) |
| `--cookies-from-browser firefox` | use your logged-in browser session (Instagram, age-gated videos) |
| `--workers N` | videos processed at once (default 4; use 1 if a platform keeps refusing) |
| `--dry-run` | list what would be processed |

One-off videos: `creator-skill transcribe <url> [<url> ...]`.

## Creator profile

`creators/<slug>/profile.json`:

```json
{
  "name": "Ana Example",
  "lang": "en",
  "tiktok": "@ana",
  "youtube": "@ana",
  "instagram": "ana"
}
```

For YouTube, a handle covers Shorts and long-form. Use the tab URL
(`https://www.youtube.com/@ana/videos`) to skip Shorts, which are often copies of the TikToks.

Instagram Reels can't be listed automatically at the moment, because yt-dlp's profile support is
broken. Paste Reel URLs, one per line, into `creators/<slug>/instagram_urls.txt`.

## Output

```
creators/<slug>/
  profile.json
  transcripts/<platform>_<id>.md   # metadata frontmatter (url, date, views, source) + transcript
  index.jsonl                      # one line per unique video, with every cross-post URL
  notes/<key>.md                   # per-video extraction
  skill/<skill-name>/
    SKILL.md                       # when to use, core principles, methods, do/don't, examples
    references/topics/*.md         # detail per topic, loaded on demand
    references/voice.md            # hooks, structures, phrase bank, example scripts (voice mode)
    references/sources.md          # every cited video with its links
```

Check a generated skill with `creator-skill check <slug> creators/<slug>/skill/<skill-name>`. It
checks the frontmatter and length, and that every video the skill cites exists.
`creator-skill stats <slug>` reports how many note quotes match the transcripts word for word.

`creators/` is git-ignored. The transcripts are other people's content, so keep them to
yourself and credit the creator when you share a skill.

## Troubleshooting

- `creator-skill doctor` fails: run the `fix:` command it prints, then run doctor again.
- "<platform> is refusing requests": you've been rate limited or hit a bot check. Progress is
  saved. Wait an hour and rerun the same command, or add `--cookies-from-browser firefox`. The
  tool doesn't try to get around platform limits.
- Instagram fails with "login required": Reels need cookies. Use
  `--cookies-from-browser firefox` (or chrome/safari) while logged in to Instagram in that
  browser. On macOS, Chrome asks for Keychain access and Safari needs Full Disk Access for your
  terminal, so Firefox is the easiest. Heavy scraping can get your own account flagged, so keep
  it to a handful of Reels.
- YouTube downloads fail but captions work: YouTube needs deno and yt-dlp-ejs, which doctor
  checks for. Upgrade yt-dlp first: `uv pip install -U "yt-dlp[default,deno]"`.
- Slow transcription: on Apple Silicon, install ffmpeg (`brew install ffmpeg`) and the `mac`
  extra to switch to mlx-whisper, or use `--model tiny`. Videos with platform captions skip
  Whisper entirely.
- Something stopped working on one platform: platforms change often. Upgrade yt-dlp first.

## Development

```bash
ruff check . && ruff format --check . && pytest   # unit tests, no network
pytest -m live                                    # one real YouTube Short
```

The architecture, the decisions behind it and the house rules are in [AGENTS.md](AGENTS.md).

## Licence

[MIT](LICENSE). Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp),
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) and
[mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper).
