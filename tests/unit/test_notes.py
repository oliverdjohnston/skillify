"""Agent-side helpers: notes-todo batching, topic tallies, sources and stats."""

import json

import pytest

from tests.conftest import add_transcript
from understudy import dedupe, notes


def add_video(base, vid, words, date_ts, views=10, platform="tiktok"):
    text = " ".join(f"{vid}w{i}" for i in range(words))
    add_transcript(base, platform, vid, text, title=f"T|{vid}", timestamp=date_ts, views=views)


def add_note(base, key, topics, content_type="tutorial", complete=True, sponsored="false"):
    (base / "notes").mkdir(exist_ok=True)
    body = "## Claims\n- a claim\n" if complete else "## Voice\n"
    (base / "notes" / f"{key}.md").write_text(
        f"---\nkey: {key}\ncontent_type: {content_type}  # tutorial | opinion\n"
        f"sponsored: {sponsored}\ntopics: [{', '.join(topics)}]\n---\n\n{body}"
    )


@pytest.fixture
def base(tmp_path):
    add_video(tmp_path, "a", 400, 1_700_000_000, views=100)
    add_video(tmp_path, "b", 400, 1_700_100_000, views=50)
    add_video(tmp_path, "c", 900, 1_700_200_000, views=5)
    add_video(tmp_path, "short", 5, 1_700_300_000)
    add_video(tmp_path, "silent", 0, 1_700_400_000)
    dedupe.rebuild(tmp_path)
    return tmp_path


def test_todo_packs_by_words_and_skips_short_and_done(base):
    add_note(base, "tiktok_a", ["hooks"])
    add_note(base, "tiktok_b", ["hooks"], complete=False)  # half-written: redo
    assert notes.todo(base, max_words=1000) == {
        "remaining": 2,
        "short": [["tiktok_c"], ["tiktok_b"]],  # biggest first; 900 + 400 > 1000
        "long": [],
    }
    assert notes.todo(base, max_words=10_000, max_items=1)["short"] == [
        ["tiktok_c"],
        ["tiktok_b"],
    ]
    assert notes.todo(base)["short"] == [["tiktok_c", "tiktok_b"]]


def test_todo_long_top_keeps_most_viewed_long_videos(tmp_path):
    for vid, seconds, views in [("s", 40, 1), ("l1", 1800, 50), ("l2", 1800, 900), ("l3", 600, 10)]:
        add_transcript(tmp_path, "youtube", vid, f"{vid} " * 100, duration=seconds, views=views)
    dedupe.rebuild(tmp_path)
    todo = notes.todo(tmp_path, long_top=1)
    assert todo["short"] == [["youtube_s"]]
    assert todo["long"] == [["youtube_l2"]]  # kept apart from short videos, even if they'd fit


def test_topics_rank_non_promo_recurrence_then_views(base):
    add_note(base, "tiktok_a", ["Hooks", "editing"])
    add_note(base, "tiktok_b", ["hooks"], content_type="promo")
    add_note(base, "tiktok_c", ["editing", "gear"], sponsored="true")
    rows = {r["tag"]: r for r in notes.topics(base)}
    # sponsored is not promo: editing has 2 supporting videos, hooks 1, gear 1 (fewer views)
    assert [r["tag"] for r in notes.topics(base)] == ["editing", "hooks", "gear"]
    assert rows["hooks"] | {"keys": None} == {
        "tag": "hooks",
        "videos": 2,
        "promo": 1,
        "views": 150,
        "newest": "2023-11-16",
        "keys": None,
    }
    assert [v["key"] for v in notes.videos_for(base, {"editing"})] == ["tiktok_c", "tiktok_a"]


def test_sources_list_every_noted_video_with_links(base):
    add_note(base, "tiktok_a", ["hooks"])
    md = notes.sources_markdown(base, "Ana")
    assert "| tiktok_a | 2023-11-14 | T/a | 100 | tutorial | [tiktok](https://tiktok/a) |" in md
    assert "tiktok_b" not in md


def test_quote_check_counts_verbatim_quotes(base):
    add_note(base, "tiktok_a", ["hooks"])
    note = base / "notes" / "tiktok_a.md"
    note.write_text(
        note.read_text() + '- real — "aw1 aw2 aw3 aw4 aw5"\n- fake — "words never said here"\n'
    )
    assert notes.quote_check(base) == (1, 2)


def test_stats(base):
    add_note(base, "tiktok_a", ["hooks"], content_type="promo")
    s = notes.stats(base)
    assert (s["transcripts"], s["no_speech"], s["unique_videos"], s["cross_posts_merged"]) == (
        5,
        1,
        4,
        0,
    )
    assert (s["too_short_for_notes"], s["notes"], s["promo"], s["sponsored"]) == (1, 1, 1, 0)
    json.dumps(s)


def write_skill(root, name="ana-hooks", body="Open with the result [tiktok_a].\n", lines=10):
    skill = root / name
    (skill / "references").mkdir(parents=True)
    (skill / "references" / "sources.md").write_text("| tiktok_zzz |\n")  # not checked
    filler = "\n" * lines
    (skill / "SKILL.md").write_text(
        "---\nname: ana-hooks\ndescription: Ana's hook methods. Use when writing hooks.\n---\n"
        + body
        + filler
    )
    return skill


def test_check_skill_passes_a_good_skill(base, tmp_path):
    assert notes.check_skill(base, write_skill(tmp_path / "out")) == []


def test_check_skill_reports_problems(base, tmp_path):
    skill = write_skill(
        tmp_path / "out", name="wrong-name", body="Made up [youtube_nope].\n", lines=500
    )
    problems = notes.check_skill(base, skill)
    assert any("match the folder" in p for p in problems)
    assert any("lines" in p for p in problems)
    assert "SKILL.md cites unknown video youtube_nope" in problems


def test_none_notes_are_complete_but_add_no_topics(base):
    add_note(base, "tiktok_a", ["background-music"], content_type="none")
    assert "tiktok_a" not in sum(notes.todo(base)["short"], [])
    assert notes.topics(base) == []
    assert notes.stats(base)["no_content"] == 1


def test_todo_fills_batches_around_long_videos(tmp_path):
    for i, words in enumerate([900, 100, 900, 100, 900, 100]):
        text = " ".join(f"v{i}w{j}" for j in range(words))  # distinct, so dedupe keeps all
        add_transcript(tmp_path, "youtube", f"v{i}", text, timestamp=1_700_000_000 + i)
    dedupe.rebuild(tmp_path)
    batches = notes.todo(tmp_path, max_words=1000)["short"]
    assert len(batches) == 3 and all(len(b) == 2 for b in batches)  # not 1+1+1+1+1+1
