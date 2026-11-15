"""The only module that talks to yt-dlp: listing, metadata, captions, audio, block detection."""

import html
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

from .models import Video

OLD_RUN_STOP = 5  # pinned posts (TikTok allows 3) can be old, so stop only after a run of old ones
SUB_FORMATS = ("vtt", "srt")
# shortcut: TikTok keys captions by ISO 639-2 ("eng-US"); add languages as creators need them
LANG3 = {"en": "eng", "es": "spa", "pt": "por", "fr": "fra", "de": "deu", "it": "ita"}
BLOCK_MARKERS = (
    "http error 429",
    "too many requests",
    "sign in to confirm",
    "login required",
    "rate-limit reached",
    "ip address is blocked",
    "keeps sending the same page",
)
SKIP_LIVE = {"is_upcoming", "is_live", "post_live"}
SKIP_AVAILABILITY = {"subscriber_only", "premium_only", "needs_auth"}
MERGE_FIELDS = ("title", "description", "timestamp", "duration", "views", "likes")


class Blocked(Exception):
    """The platform is refusing requests (rate limit, bot check or login wall)."""


_cookies: dict = {}
_client: YoutubeDL | None = None


def configure(cookies_from_browser: str | None = None, cookies: Path | None = None) -> None:
    """Set cookies for every later request. Needed for Instagram and age-gated videos."""
    global _client
    _cookies.clear()
    if cookies_from_browser:
        _cookies["cookiesfrombrowser"] = (cookies_from_browser,)
    if cookies:
        _cookies["cookiefile"] = str(cookies)
    _client = None


def _backoff(attempt: int) -> float:
    return min(60, 5 * 2**attempt)


def _params(**extra: object) -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # without these, extractors silently return no captions at all
        "writesubtitles": True,
        "writeautomaticsub": True,
        "sleep_interval_requests": 1,
        "retries": 3,
        "extractor_retries": 3,
        "retry_sleep_functions": {"http": _backoff, "extractor": _backoff, "fragment": _backoff},
        "extractor_args": {"youtubetab": {"approximate_date": [""]}},
        **_cookies,
        **extra,
    }


def _ydl() -> YoutubeDL:
    global _client
    if _client is None:
        _client = YoutubeDL(_params())
    return _client


def _raise_if_blocked(error: Exception) -> None:
    if any(marker in str(error).lower() for marker in BLOCK_MARKERS):
        raise Blocked(str(error)) from error


def list_entries(url: str, platform: str) -> Iterator[Video]:
    """Yield videos from a profile or channel tab, newest first; pages are fetched lazily."""
    try:
        result = _ydl().extract_info(url, download=False, process=False)
        for entry in result.get("entries") or ():
            if not entry or not entry.get("id"):
                continue
            if entry.get("live_status") in SKIP_LIVE:
                continue
            if entry.get("availability") in SKIP_AVAILABILITY:
                continue
            yield Video.from_info(platform, entry)
    except (DownloadError, ExtractorError) as e:
        _raise_if_blocked(e)
        raise


def full_info(video: Video) -> dict:
    """Fetch the full metadata once, and fill in whatever the listing lacked."""
    if video.info is None:
        try:
            info = _ydl().extract_info(video.url, download=False, process=False)
            while info.get("_type") == "url":  # short links (vm.tiktok.com) resolve in steps
                info = _ydl().extract_info(info["url"], download=False, process=False)
        except (DownloadError, ExtractorError) as e:
            _raise_if_blocked(e)
            raise
        video.info = info
        full = Video.from_info(video.platform, info)
        video.id = video.id or full.id  # never change a known id: it is the resume key
        video.url = full.url or video.url
        for name in MERGE_FIELDS:
            value = getattr(full, name)
            if value not in (None, ""):
                setattr(video, name, value)
    return video.info


def pick_track(subtitles: dict, automatic: dict, lang: str) -> tuple[str, dict] | None:
    """Choose captions in the creator's own speech, never a machine translation."""
    manual = {k: v for k, v in subtitles.items() if k != "live_chat"}
    wanted = {lang, LANG3.get(lang, lang)}
    keys = [k for k in manual if k.split("-")[0].lower() in wanted]
    keys += [k for k in automatic if k.endswith("-orig")]  # YouTube's speech recognition
    if len(manual) == 1:
        keys += list(manual)  # TikTok's only track is its own speech recognition
    for key in keys:
        tracks = manual.get(key) or automatic.get(key) or []
        for ext in SUB_FORMATS:
            for track in tracks:
                if track.get("ext") == ext and (track.get("data") or track.get("url")):
                    return key, track
    return None


_TAG = re.compile(r"<[^>]+>")
_NOISE = re.compile(r"\[[^\]]*\]|♪")
_HEADERS = ("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")


def clean_subtitles(raw: str) -> str:
    """Turn VTT/SRT into plain text, dropping timings, tags and YouTube's rolling repeats."""
    kept: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.isdigit() or "-->" in line or line.startswith(_HEADERS):
            continue
        line = " ".join(_NOISE.sub(" ", html.unescape(_TAG.sub("", line))).split())
        if line and line not in kept[-2:]:
            kept.append(line)
    return " ".join(kept)


def captions(video: Video, lang: str = "en") -> tuple[str, str] | None:
    """Return (text, caption language) from the platform's own captions, or None."""
    info = full_info(video)
    picked = pick_track(info.get("subtitles") or {}, info.get("automatic_captions") or {}, lang)
    if not picked:
        return None
    track_lang, track = picked
    raw = track.get("data")
    if raw is None:
        try:  # fetch now: TikTok caption URLs are signed and expire
            raw = _ydl().urlopen(track["url"]).read().decode("utf-8", "replace")
        except Exception as e:  # a failed caption fetch just means falling back to Whisper
            _raise_if_blocked(e)
            return None
    text = clean_subtitles(raw)
    return (text, track_lang) if text else None


def download_audio(video: Video, workdir: Path) -> Path:
    """Download the best audio-only stream (or the full file if there is none) into workdir."""
    params = _params(
        format="bestaudio/best",
        outtmpl=str(workdir / "%(id)s.%(ext)s"),
        writesubtitles=False,
        writeautomaticsub=False,
    )
    try:
        with YoutubeDL(params) as ydl:
            info = ydl.extract_info(video.url, download=True)
    except (DownloadError, ExtractorError) as e:
        _raise_if_blocked(e)
        raise
    return Path(info["requested_downloads"][0]["filepath"])


def window(
    videos: Iterable[Video], limit: int | None, since: str | None, ordered: bool = True
) -> Iterator[Video]:
    """Apply --limit and --since (YYYY-MM-DD) to a stream of videos.

    `ordered` streams are newest first, so a run of old videos ends the scan; a few old pinned
    posts at the top don't.
    """
    taken = old_run = 0
    for video in videos:
        if limit is not None and taken >= limit:
            return
        if since:
            if video.date is None:
                full_info(video)  # Shorts and Reels have no date in the listing
            if video.date and video.date < since:
                old_run += 1
                if ordered and old_run >= OLD_RUN_STOP:
                    return
                continue
            old_run = 0
        taken += 1
        yield video
