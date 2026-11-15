"""Video records and transcript files (markdown with JSON-valued frontmatter)."""

import json
import os
import textwrap
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class Video:
    """One video on one platform. `info` caches yt-dlp's full metadata and is never saved."""

    platform: str
    id: str
    url: str
    title: str = ""
    description: str = ""
    timestamp: int | None = None  # UTC epoch seconds
    duration: float | None = None
    views: int | None = None
    likes: int | None = None
    info: dict | None = field(default=None, repr=False)

    @property
    def key(self) -> str:
        return f"{self.platform}_{self.id}"

    @property
    def date(self) -> str | None:
        """Upload date as YYYY-MM-DD, if known."""
        if self.timestamp:
            return datetime.fromtimestamp(self.timestamp, UTC).strftime("%Y-%m-%d")
        day = (self.info or {}).get("upload_date")
        return f"{day[:4]}-{day[4:6]}-{day[6:8]}" if day else None

    @classmethod
    def from_info(cls, platform: str, info: dict) -> "Video":
        """Build from a yt-dlp info dict (a flat listing entry or full metadata)."""
        timestamp = info.get("timestamp")
        return cls(
            platform=platform,
            id=str(info.get("id") or ""),
            url=info.get("webpage_url") or info.get("url") or "",
            title=info.get("title") or "",
            description=info.get("description") or "",
            timestamp=int(timestamp) if timestamp else None,
            duration=info.get("duration"),
            views=info.get("view_count"),
            likes=info.get("like_count"),
        )


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file so an interrupted run never leaves a half-written file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_transcript(path: Path, video: Video, text: str, **extra: object) -> None:
    """Save metadata as frontmatter plus the clean transcript text."""
    meta = {
        "key": video.key,
        "platform": video.platform,
        "id": video.id,
        "url": video.url,
        "title": video.title,
        "description": video.description,
        "date": video.date,
        "duration": video.duration,
        "views": video.views,
        "likes": video.likes,
        "words": len(text.split()),
        **extra,
    }
    front = "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in meta.items())
    write_atomic(path, f"---\n{front}---\n\n{textwrap.fill(text, 100)}\n")


def read_transcript(path: Path) -> tuple[dict, str]:
    """Return (metadata, transcript text) from a file written by write_transcript."""
    _, front, body = path.read_text(encoding="utf-8").split("---\n", 2)
    meta = {}
    for line in front.splitlines():
        if line:
            key, value = line.split(": ", 1)
            meta[key] = json.loads(value)
    return meta, " ".join(body.split())
