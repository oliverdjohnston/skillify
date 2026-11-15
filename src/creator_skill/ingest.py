"""Creator profiles and ingestion: list videos, captions or Whisper, transcripts, dedupe.

A transcript file existing means that video is done, so any run can be interrupted and resumed.
"""

import json
import random
import re
import tempfile
import time
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from types import ModuleType

from . import dedupe, transcribe, ytdlp
from .models import Video, write_atomic, write_transcript
from .providers import PROVIDERS, for_url

CREATORS_DIR = Path("creators")
MAX_TRIES = 3
# shortcut: a fixed 4 parallel videos was fine on TikTok in testing; lower it if platforms block
DEFAULT_WORKERS = 4


def creator_dir(slug: str) -> Path:
    return CREATORS_DIR / slug


def load_profile(slug: str) -> dict:
    path = creator_dir(slug) / "profile.json"
    if not path.exists():
        raise SystemExit(f"No creator '{slug}'. Add one with: creator-skill creator add {slug} ...")
    return json.loads(path.read_text(encoding="utf-8"))


def save_profile(slug: str, **fields: str | None) -> dict:
    """Create or update creators/<slug>/profile.json; None values are left unchanged."""
    path = creator_dir(slug) / "profile.json"
    profile = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"name": slug}
    profile.update({k: v for k, v in fields.items() if v is not None})
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    return profile


def migrate_accounts(accounts: Path = Path("accounts.json")) -> list[str]:
    """Turn the old accounts.json (TikTok URLs) into creator profiles, then rename it."""
    if not accounts.exists():
        return []
    slugs = []
    for entry in json.loads(accounts.read_text(encoding="utf-8")).get("profiles", []):
        handle = re.search(r"@([\w.-]+)", entry.get("url", ""))
        if handle:
            slug = re.sub(r"[^a-z0-9-]+", "-", handle[1].lower()).strip("-")
            save_profile(slug, name=entry.get("name") or handle[1], tiktok="@" + handle[1])
            slugs.append(slug)
    accounts.rename(accounts.with_name("accounts.json.migrated"))
    return slugs


def process_video(provider: ModuleType, video: Video, out_dir: Path, lang: str, model: str) -> dict:
    """Write one transcript, preferring platform captions over Whisper; return its metadata."""
    ytdlp.full_info(video)
    caption = provider.fetch_captions(video, lang)
    if caption:
        text, used = caption
        extra = {"source": "caption", "lang": used}
    else:
        with tempfile.TemporaryDirectory() as tmp:
            text, used = transcribe.transcribe(provider.download_audio(video, Path(tmp)), model)
        extra = {"source": "whisper", "lang": used, "model": f"{transcribe.backend()}:{model}"}
        if used and used[:2].lower() != lang[:2].lower():
            # Whisper invents text in random languages on music-only clips, so treat as silent.
            # shortcut: also drops genuine other-language videos; set the profile's "lang" to match
            extra["dropped"] = f"Whisper heard '{used}' but the creator speaks '{lang}'"
            text = ""
    write_transcript(out_dir / f"{video.key}.md", video, text, **extra)
    return {"words": len(text.split()), **extra}


def _job(provider: ModuleType, video: Video, out_dir: Path, lang: str, model: str) -> dict:
    try:
        return process_video(provider, video, out_dir, lang, model)
    finally:
        time.sleep(random.uniform(*provider.DELAY))  # every worker keeps the polite pause


def ingest(
    slug: str,
    platforms: list[str] | None = None,
    limit: int | None = None,
    since: str | None = None,
    model: str = transcribe.DEFAULT_MODEL,
    dry_run: bool = False,
    workers: int = DEFAULT_WORKERS,
) -> Counter:
    """Transcribe everything new for a creator on each platform, then rebuild index.jsonl.

    Listing runs on this thread; up to `workers` videos are fetched and transcribed at once.
    """
    profile = load_profile(slug)
    lang = profile.get("lang", "en")
    base = creator_dir(slug)
    out_dir = base / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = base / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"failed": {}}
    done = {p.stem for p in out_dir.glob("*.md")}
    counts: Counter = Counter()

    def collect(running: dict[Future, Video], futures: Iterable[Future]) -> None:
        for future in futures:
            video = running.pop(future)
            try:
                result = future.result()
            except ytdlp.Blocked:
                raise
            except Exception as e:
                tries = state["failed"].get(video.key, {}).get("tries", 0) + 1
                print(f"  FAILED {video.key}: {e}")
                state["failed"][video.key] = {"error": str(e)[:300], "tries": tries}
                counts["failed"] += 1
            else:
                print(f"  {video.key}  {result['source']}  {result['words']} words", flush=True)
                counts[result["source"]] += 1
                done.add(video.key)
                state["failed"].pop(video.key, None)
            write_atomic(state_path, json.dumps(state, indent=2) + "\n")

    for name in platforms or list(PROVIDERS):
        provider = PROVIDERS[name]
        handle = profile.get(name) or ""
        if not handle and not (base / f"{name}_urls.txt").exists():
            continue
        print(f"== {name} {handle}")
        try:
            with ThreadPoolExecutor(max(1, workers)) as pool:
                running: dict[Future, Video] = {}
                try:
                    for video in provider.list_videos(handle, limit, since, base):
                        if video.key in done:
                            counts["already done"] += 1
                            continue
                        if state["failed"].get(video.key, {}).get("tries", 0) >= MAX_TRIES:
                            counts["gave up"] += 1
                            continue
                        if dry_run:
                            print(f"  {video.key}  {video.date or '?'}  {video.title[:60]}")
                            counts["listed"] += 1
                            continue
                        running[pool.submit(_job, provider, video, out_dir, lang, model)] = video
                        if len(running) >= workers:
                            collect(running, wait(running, return_when=FIRST_COMPLETED).done)
                finally:  # record work already in flight, even when listing is blocked
                    collect(running, list(running))
        except ytdlp.Blocked as e:
            counts["blocked"] += 1
            print(
                f"  {name} is refusing requests: {str(e)[:200]}\n"
                "  Progress is saved. Wait a while and rerun (try --workers 1), or rerun with "
                "--cookies-from-browser firefox (uses your logged-in session)."
            )
    if not dry_run:
        counts["unique videos"] = len(dedupe.rebuild(base))
    return counts


def transcribe_urls(
    urls: list[str], slug: str = "adhoc", model: str = transcribe.DEFAULT_MODEL
) -> None:
    """Transcribe specific video URLs into a creator folder (default: creators/adhoc)."""
    base = creator_dir(slug)
    profile = load_profile(slug) if (base / "profile.json").exists() else save_profile(slug)
    out_dir = base / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    for url in urls:
        try:
            provider = for_url(url)
            video = Video(provider.NAME, "", url)
            ytdlp.full_info(video)
            path = out_dir / f"{video.key}.md"
            if path.exists():
                print(f"  {video.key}  already done: {path}")
                continue
            result = process_video(provider, video, out_dir, profile.get("lang", "en"), model)
            print(f"  {video.key}  {result['source']}  {result['words']} words -> {path}")
        except Exception as e:
            print(f"  FAILED {url}: {e}")
    dedupe.rebuild(base)
