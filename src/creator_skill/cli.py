"""Command-line interface: creator-skill <command>."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import doctor, ingest, notes, transcribe, ytdlp
from .ingest import DEFAULT_WORKERS
from .providers import PROVIDERS


def _date(value: str) -> str:
    return date.fromisoformat(value).isoformat()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="creator-skill",
        description="Turn a creator's TikTok, YouTube and Instagram videos into transcripts, "
        "notes and an agent skill.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check your setup and print fixes")

    creator = sub.add_parser("creator", help="add, edit or list creator profiles")
    csub = creator.add_subparsers(dest="action", required=True)
    add = csub.add_parser("add", help="create or update creators/<slug>/profile.json")
    add.add_argument("slug")
    add.add_argument("--name")
    add.add_argument("--lang", help="language the creator speaks (default: en)")
    for name in PROVIDERS:
        add.add_argument(f"--{name}", help=f"{name} handle or URL")
    csub.add_parser("list", help="list creators")

    def network_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--model", default=transcribe.DEFAULT_MODEL, help="Whisper model size")
        cookies = p.add_mutually_exclusive_group()
        cookies.add_argument(
            "--cookies-from-browser",
            metavar="BROWSER",
            help="use your logged-in session (firefox, chrome, safari...) for Instagram/age-gated",
        )
        cookies.add_argument("--cookies", type=Path, metavar="FILE", help="Netscape cookies.txt")

    ingest = sub.add_parser("ingest", help="transcribe everything new for a creator")
    ingest.add_argument("slug")
    ingest.add_argument("--platform", action="append", choices=list(PROVIDERS), help="repeatable")
    ingest.add_argument(
        "--limit", type=int, help="newest N videos per platform (per tab on YouTube)"
    )
    ingest.add_argument("--since", type=_date, metavar="YYYY-MM-DD", help="skip older videos")
    ingest.add_argument("--dry-run", action="store_true", help="list videos without processing")
    ingest.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="videos processed at once (default %(default)s; 1 = gentlest)",
    )
    network_flags(ingest)

    adhoc = sub.add_parser("transcribe", help="transcribe specific video URLs")
    adhoc.add_argument("urls", nargs="+")
    adhoc.add_argument("--creator", default="adhoc", help="creator folder to save into")
    network_flags(adhoc)

    todo = sub.add_parser("notes-todo", help="batches of videos that still need notes (JSON)")
    todo.add_argument("slug")
    todo.add_argument("--max-words", type=int, default=15000, help="transcript words per batch")
    todo.add_argument("--max-items", type=int, default=25, help="videos per batch")

    topics = sub.add_parser("topics", help="topic tags across a creator's notes")
    topics.add_argument("slug")
    topics.add_argument("--tags", help="comma-separated tags: list their videos (JSON) instead")

    sources = sub.add_parser("sources", help="write references/sources.md for a skill")
    sources.add_argument("slug")
    sources.add_argument("--out", type=Path, required=True, help="path of sources.md to write")

    stats = sub.add_parser("stats", help="counts for a creator (JSON)")
    stats.add_argument("slug")

    check = sub.add_parser("check", help="validate a generated skill folder")
    check.add_argument("slug")
    check.add_argument("skill_dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    base = ingest.creator_dir(args.slug) if hasattr(args, "slug") else None
    if args.command == "doctor":
        sys.exit(doctor.main())
    elif args.command == "creator":
        for slug in ingest.migrate_accounts():
            print(f"Migrated accounts.json profile -> creators/{slug}/profile.json")
        if args.action == "add":
            fields = {name: getattr(args, name) for name in PROVIDERS}
            profile = ingest.save_profile(args.slug, name=args.name, lang=args.lang, **fields)
            print(f"Saved creators/{args.slug}/profile.json: {profile}")
        else:
            for path in sorted(ingest.CREATORS_DIR.glob("*/profile.json")):
                print(f"{path.parent.name}: {path.read_text(encoding='utf-8').strip()}")
    elif args.command == "notes-todo":
        print(json.dumps(notes.todo(base, args.max_words, args.max_items)))
    elif args.command == "stats":
        print(json.dumps(notes.stats(base), indent=2))
    elif args.command == "check":
        problems = notes.check_skill(base, args.skill_dir)
        print("\n".join(f"- {p}" for p in problems) or f"{args.skill_dir} looks good.")
        sys.exit(1 if problems else 0)
    elif args.command == "sources":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        name = ingest.load_profile(args.slug).get("name", args.slug)
        args.out.write_text(notes.sources_markdown(base, name), encoding="utf-8")
        print(f"Wrote {args.out}")
    elif args.command == "topics" and args.tags:
        tags = {t.strip() for t in args.tags.split(",") if t.strip()}
        print(json.dumps(notes.videos_for(base, tags), indent=1, ensure_ascii=False))
    elif args.command == "topics":
        print("| tag | videos | promo | views | newest |\n|---|---|---|---|---|")
        for row in notes.topics(base):
            print(
                f"| {row['tag']} | {row['videos']} | {row['promo']} | {row['views']:,} "
                f"| {row['newest'] or '?'} |"
            )
    else:
        ytdlp.configure(args.cookies_from_browser, args.cookies)
        if args.command == "transcribe":
            ingest.transcribe_urls(args.urls, args.creator, args.model)
            return
        counts = ingest.ingest(
            args.slug, args.platform, args.limit, args.since, args.model, args.dry_run, args.workers
        )
        print("\nSummary:", ", ".join(f"{v} {k}" for k, v in counts.items()) or "nothing to do")


if __name__ == "__main__":
    main()
