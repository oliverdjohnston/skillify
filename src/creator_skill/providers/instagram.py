"""Instagram Reels from a URL list, because yt-dlp's profile listing is broken.

Put one Reel URL per line in creators/<slug>/instagram_urls.txt. Instagram exposes no captions,
so every Reel goes through Whisper. Reels often need --cookies-from-browser.
"""

import re
from collections.abc import Iterator
from pathlib import Path

from .. import ytdlp
from ..models import Video

NAME = "instagram"
DOMAINS = ("instagram.com",)
DELAY = (8.0, 15.0)
URL_FILE = "instagram_urls.txt"
_REEL = re.compile(r"instagram\.com/(?:[\w.]+/)?(?:reels?|p)/([\w-]+)")


def list_videos(
    handle: str, limit: int | None, since: str | None, creator_dir: Path
) -> Iterator[Video]:
    path = creator_dir / URL_FILE
    if not path.exists():
        print(f"  instagram: yt-dlp can't list profiles; add Reel URLs to {path}")
        return
    seen: set[str] = set()
    videos = []
    for match in _REEL.finditer(path.read_text(encoding="utf-8")):
        code = match[1]
        if code not in seen:
            seen.add(code)
            videos.append(Video(NAME, code, f"https://www.instagram.com/reel/{code}/"))
    yield from ytdlp.window(videos, limit, since, ordered=False)


def fetch_captions(video: Video, lang: str = "en") -> None:
    return None


download_audio = ytdlp.download_audio
