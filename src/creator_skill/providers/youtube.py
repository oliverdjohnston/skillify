"""YouTube: Shorts and long-form uploads (separate channel tabs), captions and audio."""

import re
from collections.abc import Iterator
from pathlib import Path

from .. import ytdlp
from ..models import Video

NAME = "youtube"
DOMAINS = ("youtube.com", "youtu.be")
DELAY = (2.0, 5.0)
TABS = ("shorts", "videos")  # the bare channel URL returns nested tabs, so list each one


def channel_url(handle: str) -> str:
    if handle.startswith("http"):
        return re.sub(r"/(videos|shorts|streams|featured)/?$", "", handle.rstrip("/"))
    return f"https://www.youtube.com/@{handle.lstrip('@')}"


def list_videos(
    handle: str, limit: int | None, since: str | None, creator_dir: Path
) -> Iterator[Video]:
    """--limit applies per tab: Shorts have no listing dates, so tabs can't be merged by date."""
    base = channel_url(handle)
    for tab in TABS:
        try:
            yield from ytdlp.window(ytdlp.list_entries(f"{base}/{tab}", NAME), limit, since)
        except ytdlp.DownloadError as e:
            if "does not have a" not in str(e):  # e.g. "This channel does not have a shorts tab"
                raise


fetch_captions = ytdlp.captions
download_audio = ytdlp.download_audio
