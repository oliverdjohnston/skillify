"""Transcript file round trip."""

from understudy.models import Video, read_transcript, write_transcript


def test_transcript_round_trip(tmp_path):
    video = Video(
        "youtube",
        "abc",
        "https://youtu.be/abc",
        title='Say "hi" --- ok',
        description="long caption " * 100 + "#ad",
        timestamp=1_700_000_000,
        views=5,
    )
    path = tmp_path / f"{video.key}.md"
    text = "line one --- still body\n---\nmore words " * 30
    write_transcript(path, video, text, source="caption", lang="en-orig")

    meta, body = read_transcript(path)

    assert meta["title"] == 'Say "hi" --- ok'
    assert (meta["date"], meta["views"], meta["source"], meta["words"]) == (
        "2023-11-14",
        5,
        "caption",
        len(text.split()),
    )
    assert meta["description"].endswith("#ad")  # never truncated
    assert body == " ".join(text.split())
    assert not list(tmp_path.glob("*.tmp"))
