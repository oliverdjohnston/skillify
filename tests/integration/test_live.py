"""Opt-in live test against a real public, captioned YouTube Short. Run with: pytest -m live"""

import pytest

from understudy import ingest
from understudy.models import read_transcript

pytestmark = pytest.mark.live
SHORT = "https://www.youtube.com/shorts/ai1gIWacf0I"


def test_captioned_short_uses_platform_captions(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "CREATORS_DIR", tmp_path)

    ingest.transcribe_urls([SHORT], "live")

    [path] = (tmp_path / "live/transcripts").glob("*.md")
    meta, text = read_transcript(path)
    assert meta["source"] == "caption", meta
    assert meta["platform"] == "youtube" and meta["date"] and meta["views"]
    assert len(text.split()) > 20
    assert (tmp_path / "live/index.jsonl").read_text().count("\n") == 1
