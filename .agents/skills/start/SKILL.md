---
name: start
description: Set up creator-skill (Python environment, ffmpeg, Whisper) and explain how to use it. Use when someone opens this project for the first time, asks how it works, or a command fails because the environment is missing.
---

# Start

creator-skill turns everything a creator says on TikTok, YouTube and Instagram into one agent
skill built from their own words. Run every command from the project root.

## 1. Create the environment

If `uv` is installed (preferred):

```bash
uv venv -p 3.12 .venv
uv pip install -p .venv -e ".[dev]"          # add ,mac on Apple Silicon: ".[dev,mac]"
```

Otherwise:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"            # Windows: .venv\Scripts\pip install -e ".[dev]"
```

Commands use `.venv/bin/creator-skill` (Windows: `.venv\Scripts\creator-skill.exe`), so no
activation is needed. Agents often run every command in a fresh shell.

## 2. Check it

```bash
.venv/bin/creator-skill doctor
```

Fix every `FAIL` with the command it prints, then rerun until it says `All good.` A `WARN` is
optional (for example, mlx-whisper makes transcription much faster on Apple Silicon).

```bash
.venv/bin/pytest -q   # unit tests, no network; `pytest -m live` also hits YouTube once
```

## 3. Explain the workflow

| Step | Example | What happens |
|---|---|---|
| 1 | `creator https://www.tiktok.com/@ana` | Save the creator's handles (several platforms allowed) and check they resolve |
| 2 | `ingest ana 20` or `ingest ana all` | Transcribe the videos (platform captions first, Whisper otherwise), merge cross-posts, extract notes per video |
| 3 | `skillify ana both` | Synthesise the notes into one skill: their methods, their voice, or both |
| – | `transcribe <video URLs>` | One-off transcripts |

No account is needed for public TikTok and YouTube profiles. Instagram uses the cookies of a
browser where the user is logged in. Everything for a creator lives in `creators/<slug>/`.
Step 1 leads into steps 2 and 3, so the user can just start with `creator`.
