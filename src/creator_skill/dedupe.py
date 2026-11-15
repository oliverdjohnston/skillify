"""Merge cross-posts (the same clip on TikTok, Reels and Shorts) and write index.jsonl.

Captions and Whisper on the same audio differ by a few words, so texts are compared as sets of
3-word shingles. Cheap duration and length gates skip most pairs before any set maths.
"""

import json
import re
import unicodedata
from pathlib import Path

from .models import read_transcript, write_atomic

JACCARD = 0.5  # same audio scores ~0.6-0.9; different videos with a stock intro stay < 0.25
SHORT_WORDS = 15  # below this, shingles are too few to trust: require an exact match
PLATFORM_RANK = {"youtube": 0, "tiktok": 1, "instagram": 2}
_FILLER = re.compile(r"\b(?:um+|uh+|erm+)\b")


def normalise(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", text).lower())
    return " ".join(_FILLER.sub(" ", text).split())


def shingles(words: list[str], n: int = 3) -> set[tuple[str, ...]]:
    return {tuple(words[i : i + n]) for i in range(max(1, len(words) - n + 1))}


def is_duplicate(a: dict, b: dict) -> bool:
    da, db = a.get("duration"), b.get("duration")
    if da and db and abs(da - db) > max(3, 0.15 * max(da, db)):
        return False
    wa, wb = len(a["_words"]), len(b["_words"])
    if min(wa, wb) < SHORT_WORDS:
        return a["_words"] == b["_words"]
    if not 0.6 <= wa / wb <= 1 / 0.6:
        return False
    return len(a["_sh"] & b["_sh"]) / len(a["_sh"] | b["_sh"]) >= JACCARD


def rebuild(creator_dir: Path) -> list[dict]:
    """Group every transcript into unique videos and rewrite index.jsonl from scratch."""
    records = []
    for path in sorted((creator_dir / "transcripts").glob("*.md")):
        meta, text = read_transcript(path)
        if not meta.get("words"):
            continue  # silent or music-only video
        words = normalise(text).split()
        meta.pop("description", None)
        meta["transcript"] = str(path.relative_to(creator_dir))
        records.append({**meta, "_words": words, "_sh": shingles(words)})
    records.sort(key=lambda r: (r.get("date") or "9999", PLATFORM_RANK.get(r["platform"], 9)))

    groups: list[list[dict]] = []
    for record in records:
        for group in groups:
            if is_duplicate(group[0], record):
                group.append(record)
                break
        else:
            groups.append([record])

    notes = creator_dir / "notes"
    index = []
    for group in groups:
        # keep the copy that already has notes, so notes never become orphans
        canonical = next((r for r in group if (notes / f"{r['key']}.md").exists()), group[0])
        entry = {k: v for k, v in canonical.items() if not k.startswith("_")}
        entry["views_total"] = sum(r.get("views") or 0 for r in group)
        entry["copies"] = [
            {"key": r["key"], "url": r["url"], "views": r.get("views")} for r in group
        ]
        index.append(entry)
    lines = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in index)
    write_atomic(creator_dir / "index.jsonl", lines)
    return index
