"""Helpers for the agent-side steps: which videos still need notes, topic tallies, sources, stats.

Notes are written by an agent (see .agents/skills/ingest/note-template.md); this module only
reads them, so it stays lenient about formatting.
"""

import json
import re
from collections import Counter
from pathlib import Path

from .models import read_transcript

MIN_WORDS = 20  # shorter transcripts ("follow for part 2") carry nothing worth extracting


def load_index(base: Path) -> list[dict]:
    path = base / "index.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def read_note(path: Path) -> dict:
    """Frontmatter of a note as a dict; `topics` becomes a list of kebab-case tags."""
    text = path.read_text(encoding="utf-8")
    meta: dict = {"_complete": "## Claims" in text}
    if text.startswith("---"):
        for line in text.split("---", 2)[1].splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.split("#", 1)[0].strip()
    meta["topics"] = [
        re.sub(r"[^a-z0-9]+", "-", tag.strip(" '\"").lower()).strip("-")
        for tag in meta.get("topics", "").strip("[]").split(",")
        if tag.strip(" '\"")
    ]
    # only promo videos are down-weighted: a sponsored review still holds the creator's real views
    meta["promo"] = meta.get("content_type") == "promo"
    meta["sponsored"] = meta.get("sponsored", "").startswith("true")
    return meta


def _notes(base: Path) -> dict[str, dict]:
    return {p.stem: read_note(p) for p in sorted((base / "notes").glob("*.md"))}


def todo(base: Path, max_words: int = 15000, max_items: int = 25) -> dict:
    """Batches of canonical video keys that still need a complete note, packed by word count."""
    notes = _notes(base)
    batches: list[list[str]] = []
    current: list[str] = []
    words = 0
    for entry in load_index(base):
        key = entry["key"]
        if entry["words"] < MIN_WORDS or notes.get(key, {}).get("_complete"):
            continue
        if current and (words + entry["words"] > max_words or len(current) >= max_items):
            batches.append(current)
            current, words = [], 0
        current.append(key)
        words += entry["words"]
    if current:
        batches.append(current)
    return {"remaining": sum(map(len, batches)), "batches": batches}


def topics(base: Path) -> list[dict]:
    """One row per topic tag: how many videos, promo count, total views, newest date, keys."""
    index = {e["key"]: e for e in load_index(base)}
    rows: dict[str, dict] = {}
    for key, note in _notes(base).items():
        entry = index.get(key)
        if not entry or note.get("content_type") == "none":
            continue  # no longer canonical, or nothing was said
        for tag in note["topics"]:
            row = rows.setdefault(tag, {"tag": tag, "videos": 0, "promo": 0, "views": 0})
            row["videos"] += 1
            row["promo"] += note["promo"]
            row["views"] += entry["views_total"]
            row["newest"] = max(row.get("newest") or "", entry.get("date") or "")
            row.setdefault("keys", []).append(key)
    return sorted(rows.values(), key=lambda r: (-(r["videos"] - r["promo"]), -r["views"]))


def videos_for(base: Path, tags: set[str]) -> list[dict]:
    """Videos whose notes carry any of the tags, newest first, with what ranking needs."""
    notes = _notes(base)
    rows = []
    for entry in load_index(base):
        note = notes.get(entry["key"])
        if note and tags & set(note["topics"]):
            rows.append(
                {
                    "key": entry["key"],
                    "date": entry.get("date"),
                    "views_total": entry["views_total"],
                    "content_type": note.get("content_type"),
                    "promo": note["promo"],
                    "sponsored": note["sponsored"],
                    "title": entry.get("title"),
                    "note": f"notes/{entry['key']}.md",
                }
            )
    return sorted(rows, key=lambda r: r["date"] or "", reverse=True)


def sources_markdown(base: Path, name: str) -> str:
    """references/sources.md: every video with notes, with all its URLs, citeable by key."""
    notes = _notes(base)
    lines = [
        "# Sources",
        "",
        f"Every video by {name} that this skill draws on, newest first. Other files cite videos",
        "by key, e.g. `[tiktok_123]`. Cross-posts list every platform's link.",
        "",
        "| Key | Date | Title | Views | Type | Links |",
        "|---|---|---|---|---|---|",
    ]
    entries = [e for e in load_index(base) if e["key"] in notes]
    for e in sorted(entries, key=lambda e: e.get("date") or "", reverse=True):
        links = " · ".join(f"[{c['key'].split('_', 1)[0]}]({c['url']})" for c in e["copies"])
        title = (e.get("title") or "").replace("|", "/").replace("\n", " ")[:80]
        kind = notes[e["key"]].get("content_type", "")
        lines.append(
            f"| {e['key']} | {e.get('date') or '?'} | {title} | {e['views_total']:,} "
            f"| {kind} | {links} |"
        )
    return "\n".join(lines) + "\n"


def stats(base: Path) -> dict:
    """Counts for the end-of-run reports."""
    metas = [read_transcript(p)[0] for p in sorted((base / "transcripts").glob("*.md"))]
    spoken = [m for m in metas if m.get("words")]
    index = load_index(base)
    notes = _notes(base)
    dates = sorted(m["date"] for m in spoken if m.get("date"))
    return {
        "transcripts": len(metas),
        "by_platform": dict(Counter(m["platform"] for m in metas)),
        "by_source": dict(Counter(m.get("source") for m in metas)),
        "no_speech": len(metas) - len(spoken),
        "unique_videos": len(index),
        "cross_posts_merged": len(spoken) - len(index),
        "too_short_for_notes": sum(e["words"] < MIN_WORDS for e in index),
        "notes": sum(n["_complete"] for n in notes.values()),
        "no_content": sum(n.get("content_type") == "none" for n in notes.values()),
        "promo": sum(n["promo"] for n in notes.values()),
        "sponsored": sum(n["sponsored"] for n in notes.values()),
        "date_range": [dates[0], dates[-1]] if dates else None,
    }


_KEY = re.compile(r"\b(?:tiktok|youtube|instagram)_[\w-]+")
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_SKILL_LINES = 400


def check_skill(base: Path, skill_dir: Path) -> list[str]:
    """Problems with a generated skill folder; an empty list means it passes."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"{skill_md} is missing"]
    text = skill_md.read_text(encoding="utf-8")
    front = text.split("---", 2)[1] if text.startswith("---") else ""
    fields = dict(
        (k.strip(), v.strip())
        for k, v in (ln.split(":", 1) for ln in front.splitlines() if ":" in ln)
    )
    problems = []
    name = fields.get("name", "")
    if name != skill_dir.name or not _NAME.fullmatch(name) or len(name) > 64:
        problems.append("frontmatter name must be lowercase-hyphenated and match the folder name")
    if not 0 < len(fields.get("description", "")) <= 1024:
        problems.append("frontmatter description must be 1-1024 characters")
    if text.count("\n") > MAX_SKILL_LINES:
        problems.append(
            f"SKILL.md has {text.count(chr(10))} lines (keep it under {MAX_SKILL_LINES})"
        )
    if not (skill_dir / "references" / "sources.md").exists():
        problems.append("references/sources.md is missing (run: creator-skill sources)")
    known = {c["key"] for e in load_index(base) for c in e["copies"]}
    for path in sorted(skill_dir.rglob("*.md")):
        if path.name == "sources.md":
            continue
        for key in sorted(set(_KEY.findall(path.read_text(encoding="utf-8"))) - known):
            problems.append(f"{path.relative_to(skill_dir)} cites unknown video {key}")
    return problems
