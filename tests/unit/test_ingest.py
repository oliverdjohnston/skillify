"""Ingest flow: captions vs Whisper, resume, failure tracking, block handling, profiles."""

import json
from types import SimpleNamespace

import pytest

from creator_skill import ingest, transcribe, ytdlp
from creator_skill.models import Video, read_transcript


@pytest.fixture
def creators(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "CREATORS_DIR", tmp_path)
    monkeypatch.setattr(ingest.time, "sleep", lambda s: None)
    monkeypatch.setattr(ytdlp, "full_info", lambda v: {})
    ingest.save_profile("ana", name="Ana", tiktok="@ana")
    return tmp_path


def fake_provider(monkeypatch, videos, captions=None, fail=(), blocked_after=None):
    calls = {"audio": 0}

    def list_videos(handle, limit, since, creator_dir):
        for i, video in enumerate(videos):
            if blocked_after is not None and i == blocked_after:
                raise ytdlp.Blocked("HTTP Error 429")
            yield video

    def fetch_captions(video, lang):
        if video.id in fail:
            raise RuntimeError("Video unavailable")
        return (captions[video.id], "en") if captions and video.id in captions else None

    def download_audio(video, workdir):
        calls["audio"] += 1
        return workdir / "a.m4a"

    provider = SimpleNamespace(
        NAME="tiktok",
        DELAY=(0, 0),
        list_videos=list_videos,
        fetch_captions=fetch_captions,
        download_audio=download_audio,
    )
    monkeypatch.setattr(ingest, "PROVIDERS", {"tiktok": provider})
    monkeypatch.setattr(transcribe, "transcribe", lambda path, model: ("whisper words here", "en"))
    return calls


def vids(*ids):
    return [
        Video("tiktok", i, f"https://t/{i}", title=f"t{i}", timestamp=1_700_000_000) for i in ids
    ]


def test_captions_first_then_whisper(creators, monkeypatch):
    calls = fake_provider(monkeypatch, vids("1", "2"), captions={"1": "caption words " * 10})
    counts = ingest.ingest("ana")
    assert (counts["caption"], counts["whisper"], calls["audio"]) == (1, 1, 1)
    meta, text = read_transcript(creators / "ana/transcripts/tiktok_2.md")
    assert (meta["source"], meta["url"], text) == ("whisper", "https://t/2", "whisper words here")
    assert meta["model"] == f"{transcribe.backend()}:{transcribe.DEFAULT_MODEL}"
    assert (creators / "ana/index.jsonl").exists()


def test_whisper_in_the_wrong_language_counts_as_silent(creators, monkeypatch):
    fake_provider(monkeypatch, vids("1"))
    monkeypatch.setattr(transcribe, "transcribe", lambda path, model: ("2.5mm x 2mm", "nn"))
    ingest.ingest("ana")
    meta, text = read_transcript(creators / "ana/transcripts/tiktok_1.md")
    assert (meta["words"], text) == (0, "")
    assert "nn" in meta["dropped"]
    assert ingest.ingest("ana")["already done"] == 1  # not retried


def test_rerun_skips_done_videos(creators, monkeypatch):
    calls = fake_provider(monkeypatch, vids("1", "2"))
    ingest.ingest("ana")
    counts = ingest.ingest("ana")
    assert counts["already done"] == 2 and calls["audio"] == 2


def test_failures_are_retried_then_given_up(creators, monkeypatch):
    fake_provider(monkeypatch, vids("1", "bad"), captions={"1": "x " * 20}, fail={"bad"})
    for _ in range(ingest.MAX_TRIES):
        assert ingest.ingest("ana")["failed"] == 1
    assert ingest.ingest("ana")["gave up"] == 1
    state = json.loads((creators / "ana/state.json").read_text())
    assert state["failed"]["tiktok_bad"]["tries"] == ingest.MAX_TRIES


def test_block_stops_the_platform_but_keeps_progress(creators, monkeypatch, capsys):
    fake_provider(monkeypatch, vids("1", "2", "3"), blocked_after=1)
    counts = ingest.ingest("ana")
    assert (counts["whisper"], counts["blocked"]) == (1, 1)
    assert "--cookies-from-browser" in capsys.readouterr().out
    assert (creators / "ana/transcripts/tiktok_1.md").exists()


def test_dry_run_writes_nothing(creators, monkeypatch):
    fake_provider(monkeypatch, vids("1"))
    assert ingest.ingest("ana", dry_run=True)["listed"] == 1
    assert not list((creators / "ana/transcripts").glob("*.md"))


def test_platforms_without_a_handle_are_skipped(creators, monkeypatch):
    fake_provider(monkeypatch, vids("1"))
    ingest.save_profile("bo", name="Bo")
    assert ingest.ingest("bo") == {"unique videos": 0}


def test_save_profile_updates_without_clearing(creators):
    ingest.save_profile("ana", youtube="@ana_yt")
    profile = ingest.load_profile("ana")
    assert profile == {"name": "Ana", "tiktok": "@ana", "youtube": "@ana_yt"}


def test_migrate_accounts(creators, tmp_path):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(
        json.dumps(
            {
                "active": None,
                "profiles": [
                    {"url": "https://www.tiktok.com/@Some.Creator", "name": "Some Creator"}
                ],
            }
        )
    )
    assert ingest.migrate_accounts(accounts) == ["some-creator"]
    assert ingest.load_profile("some-creator")["tiktok"] == "@Some.Creator"
    assert not accounts.exists() and (tmp_path / "accounts.json.migrated").exists()


def test_parallel_workers_process_everything(creators, monkeypatch):
    calls = fake_provider(monkeypatch, vids(*map(str, range(10))), captions={"0": "c " * 30})
    counts = ingest.ingest("ana", workers=4)
    assert (counts["caption"], counts["whisper"], calls["audio"]) == (1, 9, 9)
    assert len(list((creators / "ana/transcripts").glob("*.md"))) == 10


def test_block_inside_a_worker_stops_the_platform(creators, monkeypatch, capsys):
    fake_provider(monkeypatch, vids("1", "2", "3"))

    def blocked(path, model):
        raise ytdlp.Blocked("HTTP Error 429")

    monkeypatch.setattr(transcribe, "transcribe", blocked)
    counts = ingest.ingest("ana", workers=1)
    assert counts["blocked"] == 1 and counts["failed"] == 0
    assert "refusing requests" in capsys.readouterr().out


def test_listing_finishes_before_any_video_is_processed(creators, monkeypatch):
    calls = fake_provider(monkeypatch, vids("1", "2", "3"))
    listed = {"done": False}
    inner = ingest.PROVIDERS["tiktok"].list_videos

    def list_videos(*args):
        yield from inner(*args)
        listed["done"] = True

    def download_audio(video, workdir):
        assert listed["done"], "processing started before the listing finished"
        calls["audio"] += 1
        return workdir / "a.m4a"

    ingest.PROVIDERS["tiktok"].list_videos = list_videos
    ingest.PROVIDERS["tiktok"].download_audio = download_audio
    assert ingest.ingest("ana")["whisper"] == 3


def test_platforms_run_in_parallel(creators, monkeypatch):
    import threading

    fake_provider(monkeypatch, vids("1", "2"))
    both_listing = threading.Barrier(2, timeout=5)  # opens only if both platforms list at once

    def provider_for(name):
        def list_videos(handle, limit, since, creator_dir):
            both_listing.wait()
            yield Video(name, "1", f"https://{name}/1")

        return SimpleNamespace(
            **{**vars(ingest.PROVIDERS["tiktok"]), "NAME": name, "list_videos": list_videos}
        )

    monkeypatch.setattr(ingest, "PROVIDERS", {n: provider_for(n) for n in ("tiktok", "youtube")})
    ingest.save_profile("ana", youtube="@ana")
    counts = ingest.ingest("ana")
    assert counts["whisper"] == 2
    assert {p.stem for p in (creators / "ana/transcripts").glob("*.md")} == {
        "tiktok_1",
        "youtube_1",
    }


def test_warns_when_a_listing_ends_early(creators, monkeypatch, capsys):
    fake_provider(monkeypatch, vids(*map(str, range(10))))
    ingest.ingest("ana")
    fake_provider(monkeypatch, vids("1", "2"))
    ingest.ingest("ana")
    assert "listed 2 videos, 10 last time" in capsys.readouterr().out
