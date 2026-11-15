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

Then activate it for the rest of the session: `source .venv/bin/activate`
(Windows: `.venv\Scripts\activate`).

## 2. Check it

```bash
creator-skill doctor
```

Fix every `FAIL` with the command it prints, then rerun until it says `All good.` A `WARN` is
optional (for example, mlx-whisper makes transcription much faster on Apple Silicon).

```bash
pytest -q          # unit tests, no network; `pytest -m live` also hits YouTube once
```

## 3. Explain the workflow

| Step | Skill | What happens |
|---|---|---|
| 1 | `creator` | Save a creator's handles in `creators/<slug>/profile.json` |
| 2 | `ingest` | Transcribe every video (platform captions first, Whisper otherwise), merge cross-posts, then extract structured notes per video |
| 3 | `skillify` | Synthesise all the notes into one skill: their methods, their voice, or both |
| – | `transcribe` | One-off transcripts of specific video URLs |

Everything for a creator lives in `creators/<slug>/`. Then ask what they want to do first,
usually adding a creator.
