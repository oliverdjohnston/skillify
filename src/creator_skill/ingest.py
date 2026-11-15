"""Creator profiles and ingestion: list videos, captions or Whisper, transcripts, dedupe.

A transcript file existing means that video is done, so any run can be interrupted and resumed.
"""

import random
import re
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from types import ModuleType

from . import dedupe, transcribe, ytdlp
from .models import Video, read_json, write_json, write_transcript
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
    return read_json(path, {})


def save_profile(slug: str, **fields: str | None) -> dict:
    """Create or update creators/<slug>/profile.json; None values are left unchanged."""
    path = creator_dir(slug) / "profile.json"
    profile = read_json(path, {"name": slug})
    profile.update({k: v for k, v in fields.items() if v is not None})
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, profile)
    return profile


def migrate_accounts(accounts: Path = Path("accounts.json")) -> list[str]:
    """Turn the old accounts.json (TikTok URLs) into creator profiles, then rename it."""
    slugs = []
    for entry in read_json(accounts, {}).get("profiles", []):
        handle = re.search(r"@([\w.-]+)", entry.get("url", ""))
        if handle:
            slug = re.sub(r"[^a-z0-9]+", "-", handle[1].lower()).strip("-")
            save_profile(slug, name=entry.get("name") or handle[1], tiktok="@" + handle[1])
            slugs.append(slug)
    if accounts.exists():
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
            # Whisper invents text in random languages on music-only clips.
            # shortcut: also drops genuine other-language speech; set the profile's "lang"
            extra["dropped"] = f"Whisper heard '{used}' but the creator speaks '{lang}'"
            text = ""
    write_transcript(out_dir / f"{video.key}.md", video, text, **extra)
    return {"words": len(text.split()), **extra}


def _job(provider: ModuleType, video: Video, out_dir: Path, lang: str, model: str) -> dict:
    try:
        return process_video(provider, video, out_dir, lang, model)
    finally:
        video.info = None  # large, and no longer needed
        time.sleep(random.uniform(*provider.DELAY))


def _line(video: Video, result: dict) -> str:
    return f"{video.key}  {result['source']}  {result['words']} words"


def ingest(
    slug: str,
    platforms: list[str] | None = None,
    limit: int | None = None,
    since: str | None = None,
    model: str = transcribe.DEFAULT_MODEL,
    dry_run: bool = False,
    workers: int = DEFAULT_WORKERS,
) -> Counter:
    """Transcribe everything new for a creator, then rebuild index.jsonl.

    Platforms run in parallel; each lists in full, then processes `workers` videos at once.
    """
    profile = load_profile(slug)
    lang = profile.get("lang", "en")
    workers = max(1, workers)
    base = creator_dir(slug)
    out_dir = base / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = base / "state.json"
    state = read_json(state_path, {"failed": {}})
    done = {p.stem for p in out_dir.glob("*.md")}
    counts: Counter = Counter()
    lock = threading.Lock()  # guards counts, state and state.json across platform threads

    def tries(key: str) -> int:
        return state["failed"].get(key, {}).get("tries", 0)

    def run(name: str) -> None:
        provider, handle = PROVIDERS[name], profile[name]
        # list fully first: a paused listing lets TikTok's page cursor expire and end early
        listed: list[Video] = []
        blocked = None
        try:
            for video in provider.list_videos(handle, limit, since, base):
                listed.append(video)
        except ytdlp.Blocked as e:  # still process what was listed
            blocked = e
        with lock:  # TikTok's listing sometimes ends early without an error
            seen = (
                f"{name} {handle}"  # keyed by handle: a different handle or tab lists differently
            )
            previous = state.setdefault("listed", {}).get(seen, 0)
            state["listed"][seen] = max(previous, len(listed))
        if not limit and not since and len(listed) < 0.9 * previous:
            print(
                f"  WARNING: {name} listed {len(listed)} videos, {previous} last time. "
                "Its listing ended early; rerun later to pick up the rest.",
                flush=True,
            )
        todo, skipped = [], Counter()
        for video in listed:
            if video.key in done:
                skipped["already done"] += 1
            elif tries(video.key) >= MAX_TRIES:
                skipped["gave up"] += 1
            else:
                todo.append(video)
        with lock:
            counts.update(skipped)
        print(f"== {name} {handle}: {len(todo)} new, {skipped['already done']} done", flush=True)
        if dry_run:
            for video in todo:
                print(f"  {video.key}  {video.date or '?'}  {video.title[:60]}")
            with lock:
                counts["listed"] += len(todo)
            return

        pending, running, finished = iter(todo), {}, 0
        with ThreadPoolExecutor(workers) as pool:
            while True:
                while len(running) < workers and (video := next(pending, None)):
                    running[pool.submit(_job, provider, video, out_dir, lang, model)] = video
                if not running:
                    break
                for future in wait(running, return_when=FIRST_COMPLETED).done:
                    video, finished = running.pop(future), finished + 1
                    progress = f"  {name} [{finished}/{len(todo)}]"
                    try:
                        result = future.result()
                    except ytdlp.Blocked as e:  # finish in-flight work, start nothing new
                        blocked, pending = blocked or e, iter(())
                        continue
                    except Exception as e:
                        print(f"{progress} FAILED {video.key}: {e}", flush=True)
                        with lock:
                            state["failed"][video.key] = {
                                "error": str(e)[:300],
                                "tries": tries(video.key) + 1,
                            }
                            counts["failed"] += 1
                            write_json(state_path, state)
                    else:
                        print(f"{progress} {_line(video, result)}", flush=True)
                        with lock:
                            counts[result["source"]] += 1
                            done.add(video.key)
                            state["failed"].pop(video.key, None)
                            write_json(state_path, state)
        if blocked:
            with lock:
                counts["blocked"] += 1
            print(
                f"  {name} is refusing requests: {str(blocked)[:200]}\n"
                "  Progress is saved. Wait a while and rerun (try --workers 1), or rerun with "
                "--cookies-from-browser firefox (uses your logged-in session)."
            )

    names = [n for n in (platforms or PROVIDERS) if profile.get(n)]
    with ThreadPoolExecutor(max(1, len(names))) as pool:
        for future in [pool.submit(run, name) for name in names]:
            future.result()  # re-raise anything unexpected
    if not dry_run:
        counts["unique videos"] = len(dedupe.rebuild(base))
    return counts


def transcribe_urls(
    urls: list[str], slug: str = "adhoc", model: str = transcribe.DEFAULT_MODEL
) -> None:
    """Transcribe specific video URLs into a creator folder (default: creators/adhoc)."""
    base = creator_dir(slug)
    lang = save_profile(slug).get("lang", "en")
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
            print(f"  {_line(video, _job(provider, video, out_dir, lang, model))} -> {path}")
        except Exception as e:
            print(f"  FAILED {url}: {e}")
    dedupe.rebuild(base)
