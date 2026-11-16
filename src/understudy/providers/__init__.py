"""Platform providers. Each module exposes the same interface:

    NAME: str                      # also the key in a creator's profile.json
    DOMAINS: tuple[str, ...]       # hosts its video URLs live on (subdomains included)
    DELAY: tuple[float, float]     # polite pause between videos, in seconds
    list_videos(handle, limit, since, creator_dir) -> Iterator[Video]   # newest first
    fetch_captions(video, lang) -> (text, lang) | None
    download_audio(video, workdir) -> Path

Adding a platform (e.g. X) means one new module plus one entry in PROVIDERS.
"""

from types import ModuleType
from urllib.parse import urlparse

from . import instagram, tiktok, youtube

PROVIDERS: dict[str, ModuleType] = {p.NAME: p for p in (tiktok, youtube, instagram)}


def for_url(url: str) -> ModuleType:
    """The provider for a video URL, e.g. https://vm.tiktok.com/abc."""
    host = urlparse(url).hostname or ""
    for provider in PROVIDERS.values():
        if any(host == d or host.endswith("." + d) for d in provider.DOMAINS):
            return provider
    raise ValueError(f"Unsupported URL (need {', '.join(PROVIDERS)}): {url}")
