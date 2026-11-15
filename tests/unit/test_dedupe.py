"""Cross-post detection and index.jsonl."""

import json

from creator_skill import dedupe
from tests.conftest import add_transcript

SCRIPT = (
    "stop writing hooks that start with hey guys because nobody cares who you are yet "
    "instead open with the result you got and the mistake that almost cost you it then "
    "show the one change you made and tell them exactly how long it took to see results"
)


def add(creator, platform, vid, text, date_ts, duration=40.0, views=100):
    add_transcript(creator, platform, vid, text, timestamp=date_ts, duration=duration, views=views)


def test_cross_posts_merge_despite_asr_differences(tmp_path):
    noisy = SCRIPT.replace("nobody cares", "no body cares").replace("exactly", "um exactly")
    noisy = noisy.replace("the mistake", "a mistake")
    add(tmp_path, "tiktok", "1", SCRIPT, 1_700_000_000, views=500)
    add(tmp_path, "instagram", "2", noisy.upper(), 1_700_100_000, duration=41.5, views=50)
    add(tmp_path, "youtube", "3", "a totally different video about editing " * 6, 1_700_200_000)

    index = dedupe.rebuild(tmp_path)

    assert len(index) == 2
    merged = next(e for e in index if len(e["copies"]) == 2)
    assert merged["key"] == "tiktok_1"  # earliest copy is canonical
    assert merged["views_total"] == 550
    assert {c["url"] for c in merged["copies"]} == {"https://tiktok/1", "https://instagram/2"}
    lines = (tmp_path / "index.jsonl").read_text().splitlines()
    assert [json.loads(line)["key"] for line in lines] == [e["key"] for e in index]


def test_different_lengths_never_merge(tmp_path):
    add(tmp_path, "tiktok", "1", SCRIPT, 1_700_000_000, duration=40)
    add(tmp_path, "youtube", "2", SCRIPT + " " + SCRIPT, 1_700_000_100, duration=600)
    assert len(dedupe.rebuild(tmp_path)) == 2


def test_short_texts_need_an_exact_match(tmp_path):
    add(tmp_path, "tiktok", "1", "follow for part two", 1_700_000_000)
    add(tmp_path, "youtube", "2", "Follow for part two!", 1_700_000_100)
    add(tmp_path, "instagram", "3", "follow for part three", 1_700_000_200)
    assert len(dedupe.rebuild(tmp_path)) == 2


def test_canonical_copy_keeps_existing_notes(tmp_path):
    add(tmp_path, "tiktok", "1", SCRIPT, 1_700_000_000)
    add(tmp_path, "youtube", "2", SCRIPT, 1_700_000_100)
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "youtube_2.md").write_text("notes")
    assert dedupe.rebuild(tmp_path)[0]["key"] == "youtube_2"


def test_silent_videos_are_left_out(tmp_path):
    add(tmp_path, "tiktok", "1", "", 1_700_000_000)
    assert dedupe.rebuild(tmp_path) == []


def test_indexed_grouping_matches_comparing_every_pair():
    import random

    rng = random.Random(7)
    vocab = [f"w{i}" for i in range(60)]
    bases = [[rng.choice(vocab) for _ in range(rng.choice([8, 30, 60]))] for _ in range(40)]
    records = []
    for i in range(300):
        words = list(rng.choice(bases))
        for _ in range(rng.randint(0, 6)):  # speech-recognition style noise
            words[rng.randrange(len(words))] = rng.choice(vocab)
        records.append(
            {
                "key": str(i),
                "duration": rng.choice([None, 30, 31, 90]),
                "_words": words,
                "_sh": dedupe.shingles(words),
            }
        )

    brute: list[list[dict]] = []
    for record in records:
        for group in brute:
            if dedupe.is_duplicate(group[0], record):
                group.append(record)
                break
        else:
            brute.append([record])

    def keys(groups):
        return [[r["key"] for r in g] for g in groups]

    assert keys(dedupe.group_records(records)) == keys(brute)
    assert len(brute) < len(records)  # the data really contains duplicates
