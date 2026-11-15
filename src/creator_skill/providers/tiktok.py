"""TikTok: profile listing, auto-captions and audio via yt-dlp."""

from collections.abc import Iterator
from pathlib import Path

from .. import ytdlp
from ..models import Video

NAME = "tiktok"
DOMAINS = ("tiktok.com",)
DELAY = (2.0, 5.0)


def list_videos(
    handle: str, limit: int | None, since: str | None, creator_dir: Path
) -> Iterator[Video]:
    url = handle if handle.startswith("http") else f"https://www.tiktok.com/@{handle.lstrip('@')}"
    return ytdlp.window(ytdlp.list_entries(url, NAME), limit, since)


fetch_captions = ytdlp.captions
download_audio = ytdlp.download_audio
