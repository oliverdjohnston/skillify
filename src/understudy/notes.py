"""Helpers for the agent-side steps: which videos still need notes, topic tallies, sources, stats.

Notes are written by an agent (see skills/ingest/note-template.md); this module only
reads them, so it stays lenient about formatting.
"""

import json
import re
from collections import Counter
from pathlib import Path

from .dedupe import normalise
from .models import read_transcript, split_frontmatter
from .providers import PROVIDERS

MIN_WORDS = 20  # e.g. "follow for part 2"
LONG_SECONDS = 180  # YouTube's Shorts limit


def load_index(base: Path) -> list[dict]:
    path = base / "index.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def read_note(path: Path) -> dict:
    """Frontmatter of a note as a dict; `topics` becomes a list of kebab-case tags."""
    text = path.read_text(encoding="utf-8")
    fields, _ = split_frontmatter(text)
    meta: dict = {k: v.split("#", 1)[0].strip() for k, v in fields.items()}  # drop # comments
    meta["_complete"] = "## Claims" in text
    meta["topics"] = [
        re.sub(r"[^a-z0-9]+", "-", tag.strip(" '\"").lower()).strip("-")
        for tag in meta.get("topics", "").strip("[]").split(",")
        if tag.strip(" '\"")
    ]
    # only promo is down-weighted: a sponsored review still holds real views
    meta["promo"] = meta.get("content_type") == "promo"
    meta["sponsored"] = meta.get("sponsored", "").startswith("true")
    return meta


def _notes(base: Path, with_content: bool = True) -> dict[str, dict]:
    """Notes by key; by default without `content_type: none` (music or noise, nothing said)."""
    notes = {p.stem: read_note(p) for p in sorted((base / "notes").glob("*.md"))}
    if with_content:
        notes = {k: n for k, n in notes.items() if n.get("content_type") != "none"}
    return notes


def todo(
    base: Path, max_words: int = 30000, max_items: int = 75, long_top: int | None = None
) -> dict:
    """Batches of canonical video keys that still need a complete note, packed by word count.

    Videos over LONG_SECONDS get their own batches under "long", so the agent can give short ones
    to a cheaper model. `long_top` keeps only the N most-viewed long videos.
    """
    notes = _notes(base, with_content=False)
    index = load_index(base)
    long = sorted(
        (e for e in index if (e.get("duration") or 0) > LONG_SECONDS),
        key=lambda e: -e["views_total"],
    )
    skip = {e["key"] for e in long[long_top:]} if long_top is not None else set()
    pending = [
        e
        for e in index
        if e["words"] >= MIN_WORDS
        and e["key"] not in skip
        and not notes.get(e["key"], {}).get("_complete")
    ]
    is_long = {e["key"] for e in long}
    return {
        "remaining": len(pending),
        "short": _pack([e for e in pending if e["key"] not in is_long], max_words, max_items),
        "long": _pack([e for e in pending if e["key"] in is_long], max_words, max_items),
    }


def _pack(entries: list[dict], max_words: int, max_items: int) -> list[list[str]]:
    """First-fit, biggest first: big transcripts otherwise leave many near-empty batches."""
    batches: list[dict] = []
    for entry in sorted(entries, key=lambda e: -e["words"]):
        for batch in batches:
            if len(batch["keys"]) < max_items and batch["words"] + entry["words"] <= max_words:
                batch["keys"].append(entry["key"])
                batch["words"] += entry["words"]
                break
        else:
            batches.append({"keys": [entry["key"]], "words": entry["words"]})
    return [b["keys"] for b in batches]


def topics(base: Path) -> list[dict]:
    """One row per topic tag: how many videos, promo count, total views, newest date, keys."""
    index = {e["key"]: e for e in load_index(base)}
    rows: dict[str, dict] = {}
    for key, note in _notes(base).items():
        entry = index.get(key)
        if not entry:
            continue
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


_QUOTE = re.compile(r'"([^"\n]{12,})"')


def quote_check(base: Path) -> tuple[int, int]:
    """(verbatim, total) quotes in notes, checked against their transcripts."""
    found = total = 0
    for note in sorted((base / "notes").glob("*.md")):
        transcript = base / "transcripts" / note.name
        if transcript.exists():
            text = normalise(read_transcript(transcript)[1])
            for quote in _QUOTE.findall(note.read_text(encoding="utf-8")):
                total += 1
                found += normalise(quote) in text
    return found, total


def stats(base: Path) -> dict:
    """Counts for the end-of-run reports."""
    metas = [read_transcript(p)[0] for p in sorted((base / "transcripts").glob("*.md"))]
    spoken = [m for m in metas if m.get("words")]
    index = load_index(base)
    notes = _notes(base, with_content=False)
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
        "quotes_verbatim": "{}/{}".format(*quote_check(base)),
    }


_KEY = re.compile(rf"\b(?:{'|'.join(PROVIDERS)})_[\w-]+")
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_SKILL_LINES = 400


def check_skill(base: Path, skill_dir: Path) -> list[str]:
    """Problems with a generated skill folder; an empty list means it passes."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"{skill_md} is missing"]
    text = skill_md.read_text(encoding="utf-8")
    fields, _ = split_frontmatter(text)
    lines = text.count("\n")
    problems = []
    name = fields.get("name", "")
    if name != skill_dir.name or not _NAME.fullmatch(name) or len(name) > 64:
        problems.append("frontmatter name must be lowercase-hyphenated and match the folder name")
    if not 0 < len(fields.get("description", "")) <= 1024:
        problems.append("frontmatter description must be 1-1024 characters")
    if lines > MAX_SKILL_LINES:
        problems.append(f"SKILL.md has {lines} lines (keep it under {MAX_SKILL_LINES})")
    if not (skill_dir / "references" / "sources.md").exists():
        problems.append("references/sources.md is missing (run: understudy sources)")
    known = {c["key"] for e in load_index(base) for c in e["copies"]}
    for path in sorted(skill_dir.rglob("*.md")):
        if path.name == "sources.md":
            continue
        for key in sorted(set(_KEY.findall(path.read_text(encoding="utf-8"))) - known):
            problems.append(f"{path.relative_to(skill_dir)} cites unknown video {key}")
    return problems
