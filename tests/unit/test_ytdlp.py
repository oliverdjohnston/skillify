"""Captions, listing windows, metadata merging and block detection."""

import pytest
from yt_dlp.utils import DownloadError

from creator_skill import ytdlp
from creator_skill.models import Video

YOUTUBE_AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000 align:start position:0%
so<00:00:00.500><c> today</c><00:00:01.000><c> we're</c>

00:00:02.000 --> 00:00:02.010 align:start position:0%
so today we're

00:00:02.010 --> 00:00:04.000 align:start position:0%
so today we're
talking<00:00:02.500><c> about</c><00:00:03.000><c> hooks</c> [Music]
"""


def test_clean_subtitles_drops_timings_tags_and_rolling_repeats():
    assert ytdlp.clean_subtitles(YOUTUBE_AUTO_VTT) == "so today we're talking about hooks"


def test_clean_subtitles_handles_srt_and_entities():
    srt = (
        "1\n00:00:00,000 --> 00:00:01,000\nRock &amp; roll\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\n♪ is back\n"
    )
    assert ytdlp.clean_subtitles(srt) == "Rock & roll is back"


VTT = [{"ext": "vtt", "url": "u"}]


@pytest.mark.parametrize(
    ("subs", "auto", "lang", "expected"),
    [
        ({"en": VTT, "ja": VTT}, {"en-orig": VTT}, "en", "en"),  # manual in creator's language
        ({"ja": VTT}, {"en-orig": VTT, "fr": VTT}, "en", "en-orig"),  # foreign manual = translation
        ({}, {"es-orig": VTT, "en": VTT}, "en", "es-orig"),  # plain auto "en" is a translation
        ({"eng-US": VTT}, {}, "en", "eng-US"),  # TikTok ISO 639-2 key
        ({"spa-ES": VTT}, {}, "en", "spa-ES"),  # TikTok's only track is its own ASR
        ({"spa-ES": VTT, "fra-FR": VTT}, {}, "en", None),  # ambiguous: use Whisper
        ({"live_chat": VTT}, {}, "en", None),
        ({"en": [{"ext": "json3", "url": "u"}]}, {}, "en", None),  # no usable format
    ],
)
def test_pick_track(subs, auto, lang, expected):
    picked = ytdlp.pick_track(subs, auto, lang)
    assert (picked[0] if picked else None) == expected


def test_pick_track_prefers_vtt_over_srt():
    tracks = [{"ext": "srt", "url": "s"}, {"ext": "vtt", "url": "v"}]
    assert ytdlp.pick_track({"en": tracks}, {}, "en")[1]["url"] == "v"


def test_captions_fetches_and_cleans(fake_ydl, tiktok_info):
    fake_ydl(
        {tiktok_info["webpage_url"]: tiktok_info}, {"https://cdn.example/cap.vtt": YOUTUBE_AUTO_VTT}
    )
    video = Video("tiktok", tiktok_info["id"], tiktok_info["webpage_url"])
    assert ytdlp.captions(video) == ("so today we're talking about hooks", "eng-US")


def test_full_info_fills_listing_gaps_once_and_keeps_id(fake_ydl, tiktok_info):
    fake = fake_ydl(
        {
            "https://vm.tiktok.com/x": {"_type": "url", "url": "https://real"},
            "https://real": tiktok_info,
        }
    )
    video = Video("tiktok", "listing-id", "https://vm.tiktok.com/x")
    ytdlp.full_info(video)
    ytdlp.full_info(video)
    assert fake.calls == ["https://vm.tiktok.com/x", "https://real"]
    assert video.id == "listing-id"  # resume key must not change
    assert (video.views, video.date, video.url) == (
        249400,
        "2026-11-14",
        tiktok_info["webpage_url"],
    )


def test_list_entries_skips_unusable_entries(fake_ydl):
    entries = [
        None,
        {"id": "a", "url": "ua"},
        {"id": "b", "live_status": "is_upcoming"},
        {"id": "c", "availability": "subscriber_only"},
        {"url": "no-id"},
    ]
    fake_ydl({"https://list": {"_type": "playlist", "entries": iter(entries)}})
    assert [v.id for v in ytdlp.list_entries("https://list", "youtube")] == ["a"]


def test_rate_limit_becomes_blocked(fake_ydl):
    fake_ydl({"https://list": DownloadError("ERROR: HTTP Error 429: Too Many Requests")})
    with pytest.raises(ytdlp.Blocked):
        list(ytdlp.list_entries("https://list", "tiktok"))


def test_other_errors_pass_through(fake_ydl):
    fake_ydl({"https://list": DownloadError("ERROR: Video unavailable")})
    with pytest.raises(DownloadError):
        list(ytdlp.list_entries("https://list", "tiktok"))


DAY = 86400
NOW = 1794619464  # 2026-11-14 UTC


def dated(i: int, days_ago: int) -> Video:
    return Video("tiktok", str(i), f"u{i}", timestamp=NOW - days_ago * DAY)


def test_window_limit():
    assert len(list(ytdlp.window((dated(i, i) for i in range(10)), 3, None))) == 3


def test_window_since_survives_old_pinned_posts():
    pinned = [dated(100 + i, 400) for i in range(3)]
    recent = [dated(i, i) for i in range(5)]
    old = [dated(200 + i, 300 + i) for i in range(20)]
    taken = list(ytdlp.window(pinned + recent + old, None, "2026-10-01"))
    assert [v.id for v in taken] == [str(i) for i in range(5)]


def test_window_stops_after_a_run_of_old_videos():
    def stream():
        for i in range(ytdlp.OLD_RUN_STOP):
            yield dated(i, 400)
        raise AssertionError("should have stopped before reading further")

    assert list(ytdlp.window(stream(), None, "2026-10-01")) == []


def test_window_unordered_scans_everything():
    videos = [dated(i, 400) for i in range(10)] + [dated(99, 1)]
    assert [v.id for v in ytdlp.window(videos, None, "2026-10-01", ordered=False)] == ["99"]


def test_window_fetches_dates_only_when_needed(monkeypatch):
    fetched = []
    monkeypatch.setattr(ytdlp, "full_info", lambda v: fetched.append(v.id) or {})
    undated = [Video("youtube", "s1", "u")]
    list(ytdlp.window(undated, None, None))
    assert fetched == []
    list(ytdlp.window(undated, None, "2026-01-01"))
    assert fetched == ["s1"]
