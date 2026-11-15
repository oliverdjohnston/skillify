"""The only module that talks to yt-dlp: listing, metadata, captions, audio, block detection."""

import html
import re
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
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
_local = threading.local()  # YoutubeDL isn't thread-safe: one client per thread
_generation = 0  # bumped by configure() to rebuild clients


def configure(cookies_from_browser: str | None = None, cookies: Path | None = None) -> None:
    """Set cookies for every later request. Needed for Instagram and age-gated videos."""
    global _generation
    _cookies.clear()
    if cookies_from_browser:
        _cookies["cookiesfrombrowser"] = (cookies_from_browser,)
    if cookies:
        _cookies["cookiefile"] = str(cookies)
    _generation += 1


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
    if getattr(_local, "generation", None) != _generation:
        _local.client, _local.generation = YoutubeDL(_params()), _generation
    return _local.client


def _raise_if_blocked(error: Exception) -> None:
    if any(marker in str(error).lower() for marker in BLOCK_MARKERS):
        raise Blocked(str(error)) from error


@contextmanager
def _blocking() -> Iterator[None]:
    """Wrap every yt-dlp call: rate limits and bot checks become Blocked, the rest pass through."""
    try:
        yield
    except (DownloadError, ExtractorError) as e:
        _raise_if_blocked(e)
        raise


def list_entries(url: str, platform: str) -> Iterator[Video]:
    """Yield videos from a profile or channel tab, newest first; pages are fetched lazily."""
    with _blocking():
        result = _ydl().extract_info(url, download=False, process=False)
        for entry in result.get("entries") or ():
            if not entry or not entry.get("id"):
                continue
            if entry.get("live_status") in SKIP_LIVE:
                continue
            if entry.get("availability") in SKIP_AVAILABILITY:
                continue
            yield Video.from_info(platform, entry)


def full_info(video: Video) -> dict:
    """Fetch the full metadata once, and fill in whatever the listing lacked."""
    if video.info is None:
        with _blocking():
            info = _ydl().extract_info(video.url, download=False, process=False)
            while info.get("_type") == "url":  # short links (vm.tiktok.com) resolve in steps
                info = _ydl().extract_info(info["url"], download=False, process=False)
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
_TIMING = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})\s*-->")


def clean_subtitles(raw: str) -> str:
    """Turn VTT/SRT into plain text, dropping timings, tags and YouTube's rolling repeats.

    Cues are sorted by start time: TikTok's caption files list them out of order.
    """
    cues: list[tuple[float, int, list[str]]] = []  # (start, file order, lines)
    for line in raw.splitlines():
        line = line.strip()
        timing = _TIMING.match(line)
        if timing:
            h, m, sec, ms = (int(g or 0) for g in timing.groups())
            cues.append((h * 3600 + m * 60 + sec + ms / 1000, len(cues), []))
            continue
        if not line or line.isdigit() or "-->" in line or line.startswith(_HEADERS):
            continue
        text = " ".join(_NOISE.sub(" ", html.unescape(_TAG.sub("", line))).split())
        if text:
            if not cues:
                cues.append((0.0, 0, []))
            cues[-1][2].append(text)
    kept: list[str] = []
    for _, _, lines in sorted(cues):
        for text in lines:
            if text not in kept[-2:]:
                kept.append(text)
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
        except Exception as e:  # fall back to Whisper
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
    with _blocking(), YoutubeDL(params) as ydl:
        info = ydl.extract_info(video.url, download=True)
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
