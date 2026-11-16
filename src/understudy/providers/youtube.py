"""YouTube: Shorts and long-form uploads (separate channel tabs), captions and audio."""

import re
from collections.abc import Iterator
from pathlib import Path

from .. import ytdlp
from ..models import Video

NAME = "youtube"
DOMAINS = ("youtube.com", "youtu.be")
DELAY = (1.0, 2.5)
TABS = ("shorts", "videos")


def channel_and_tabs(handle: str) -> tuple[str, tuple[str, ...]]:
    """A handle lists every tab; a tab URL (e.g. .../@x/videos) lists only that tab."""
    if not handle.startswith("http"):
        return f"https://www.youtube.com/@{handle.lstrip('@')}", TABS
    match = re.search(r"/(videos|shorts|streams|featured)/?$", handle)
    base = handle[: match.start()] if match else handle.rstrip("/")
    tab = match[1] if match else None
    return base, (tab,) if tab in TABS else TABS


def list_videos(
    handle: str, limit: int | None, since: str | None, creator_dir: Path
) -> Iterator[Video]:
    """--limit applies per tab: Shorts have no listing dates, so tabs can't be merged by date."""
    base, tabs = channel_and_tabs(handle)
    for tab in tabs:
        try:
            yield from ytdlp.window(ytdlp.list_entries(f"{base}/{tab}", NAME), limit, since)
        except ytdlp.DownloadError as e:
            if "does not have a" not in str(e):  # "...does not have a shorts tab"
                raise


fetch_captions = ytdlp.captions
download_audio = ytdlp.download_audio
