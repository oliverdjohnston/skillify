"""Shared fixtures: a fake yt-dlp client fed with recorded-style info dicts."""

import pytest

from creator_skill import ytdlp


class FakeYDL:
    """Stands in for yt_dlp.YoutubeDL: maps URLs to info dicts (or exceptions)."""

    def __init__(self, infos: dict, captions: dict | None = None) -> None:
        self.infos = infos
        self.captions = captions or {}
        self.calls: list[str] = []

    def extract_info(self, url: str, download: bool = False, process: bool = True) -> dict:
        self.calls.append(url)
        result = self.infos[url]
        if isinstance(result, Exception):
            raise result
        return result

    def urlopen(self, url: str):
        body = self.captions[url].encode()
        return type("Resp", (), {"read": lambda self: body})()


@pytest.fixture
def fake_ydl(monkeypatch):
    def install(infos: dict, captions: dict | None = None) -> FakeYDL:
        fake = FakeYDL(infos, captions)
        monkeypatch.setattr(ytdlp, "_client", fake)
        return fake

    return install


@pytest.fixture
def tiktok_info() -> dict:
    """Shape of yt-dlp's full TikTok info (process=False), trimmed."""
    return {
        "id": "7707831843487354143",
        "webpage_url": "https://www.tiktok.com/@creator/video/7707831843487354143",
        "title": "Three hooks that work",
        "description": "Hooks #tips",
        "timestamp": 1794619464,
        "duration": 63,
        "view_count": 249400,
        "like_count": 1200,
        "subtitles": {"eng-US": [{"url": "https://cdn.example/cap.vtt", "ext": "vtt"}]},
    }
