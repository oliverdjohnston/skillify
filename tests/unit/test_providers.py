"""Provider URL handling and the Instagram URL list."""

import pytest

from creator_skill import ytdlp
from creator_skill.models import Video
from creator_skill.providers import PROVIDERS, for_url, instagram, tiktok, youtube


@pytest.fixture
def listed(monkeypatch):
    urls: list[str] = []

    def fake_list(url, platform):
        urls.append(url)
        if url.endswith("/shorts"):
            raise ytdlp.DownloadError("ERROR: This channel does not have a shorts tab")
        yield Video(platform, url.rsplit("/", 1)[-1], url)

    monkeypatch.setattr(ytdlp, "list_entries", fake_list)
    return urls


def test_every_provider_has_the_interface():
    for provider in PROVIDERS.values():
        for attr in ("NAME", "DELAY", "list_videos", "fetch_captions", "download_audio"):
            assert hasattr(provider, attr), (provider.NAME, attr)


@pytest.mark.parametrize("handle", ["@creator", "creator", "https://www.tiktok.com/@creator"])
def test_tiktok_profile_url(listed, handle, tmp_path):
    list(tiktok.list_videos(handle, None, None, tmp_path))
    assert listed == ["https://www.tiktok.com/@creator"]


def test_youtube_lists_both_tabs_and_tolerates_a_missing_one(listed, tmp_path):
    videos = list(youtube.list_videos("https://www.youtube.com/@creator/videos", 5, None, tmp_path))
    assert listed == [
        "https://www.youtube.com/@creator/shorts",
        "https://www.youtube.com/@creator/videos",
    ]
    assert [v.id for v in videos] == ["videos"]


def test_instagram_reads_url_list(tmp_path):
    (tmp_path / "instagram_urls.txt").write_text(
        "https://www.instagram.com/reel/AbC123/?igsh=xyz\n"
        "https://instagram.com/creator/reels/AbC123/\n"  # duplicate
        "https://www.instagram.com/p/Zz9_-/\n"
        "not a url\n"
    )
    videos = list(instagram.list_videos("", None, None, tmp_path))
    assert [(v.id, v.url) for v in videos] == [
        ("AbC123", "https://www.instagram.com/reel/AbC123/"),
        ("Zz9_-", "https://www.instagram.com/reel/Zz9_-/"),
    ]
    assert instagram.fetch_captions(videos[0]) is None


def test_instagram_without_url_list_yields_nothing(tmp_path, capsys):
    assert list(instagram.list_videos("creator", None, None, tmp_path)) == []
    assert "instagram_urls.txt" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("url", "provider"),
    [
        ("https://vm.tiktok.com/ZM123/", tiktok),
        ("https://www.youtube.com/shorts/abc", youtube),
        ("https://youtu.be/abc", youtube),
        ("https://www.instagram.com/reel/abc/", instagram),
    ],
)
def test_for_url(url, provider):
    assert for_url(url) is provider


def test_for_url_rejects_lookalikes():
    with pytest.raises(ValueError):
        for_url("https://nottiktok.com/video/1")
