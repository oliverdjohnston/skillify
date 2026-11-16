---
name: start
description: 'Install or set up Understudy''s command-line tool, `understudy` (via uv), check it works, and explain how to turn a creator''s videos into a skill. Use when someone first uses these skills, asks how they work, or an `understudy` command fails because the tool isn''t installed.'
---

# Start

Understudy turns everything a creator says on TikTok, YouTube and Instagram into one agent skill
built from their own words. The skills drive a small command-line tool, `understudy`.

## 1. Get the tool

**Inside the understudy repo** (it has `pyproject.toml` and `src/understudy/`): make a local
environment.

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev,mac]"
```

The tool is then `.venv/bin/understudy` (Windows: `.venv\Scripts\understudy.exe`).

**Anywhere else** (the skills were installed with `npx skills add oliverdjohnston/understudy -g`):
install the tool once for the user. Ask first, because it installs software.

```bash
uv tool install "understudy[mac] @ git+https://github.com/oliverdjohnston/understudy"
```

The `[mac]` extra adds the faster Apple Silicon transcription, and does nothing on other
systems. The command is then `understudy`; if the PATH hasn't refreshed yet, use
`~/.local/bin/understudy`. Upgrade later with `uv tool upgrade understudy`.

If `uv` itself is missing, install it first (it is a single binary):
- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`)
- Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

No uv and the user would rather not install it? Inside the repo, plain Python works too:
`python3 -m venv .venv && .venv/bin/pip install -e .`

## 2. Check it

```bash
understudy doctor
```

Fix every `FAIL` with the command it prints, then rerun until it says `All good.` A `WARN` is
optional: for example, ffmpeg turns on the faster Apple Silicon transcription. In the repo,
`.venv/bin/pytest -q` runs the unit tests.

## 3. Explain the workflow

| Step | Example | What happens |
|---|---|---|
| 1 | `creator https://www.tiktok.com/@ana` | Save the creator's handles (several platforms allowed) and check they resolve |
| 2 | `ingest ana 20` or `ingest ana all` | Transcribe the videos (platform captions first, Whisper otherwise), merge cross-posts, extract notes per video |
| 3 | `/understudy ana both` | Synthesise the notes into one skill: their methods, their voice, or both |
| – | `transcribe <video URLs>` | One-off transcripts |

No account is needed for public TikTok and YouTube profiles. Instagram uses the cookies of a
browser where the user is logged in. Everything for a creator lives in `creators/<slug>/` under
the current folder. Step 1 leads into steps 2 and 3, so the user can just start with `creator`.
