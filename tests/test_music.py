import random

from app.services.music import list_tracks, mood_from_text, pick_track


def _make(tmp_path, names):
    for n in names:
        p = tmp_path / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")


def test_list_tracks_folder_prefix_and_other(tmp_path):
    _make(tmp_path, ["calm/a.mp3", "dramatic_b.mp3", "random.mp3", "notes.txt"])
    t = list_tracks(tmp_path)
    assert [p.name for p in t["calm"]] == ["a.mp3"]
    assert [p.name for p in t["dramatic"]] == ["dramatic_b.mp3"]
    assert [p.name for p in t["any"]] == ["random.mp3"]


def test_pick_prefers_mood(tmp_path):
    _make(tmp_path, ["calm/a.mp3", "upbeat/b.mp3"])
    for seed in range(5):
        assert pick_track(tmp_path, "upbeat", random.Random(seed)).name == "b.mp3"


def test_pick_falls_back_to_any_track(tmp_path):
    _make(tmp_path, ["calm/a.mp3"])
    assert pick_track(tmp_path, "dramatic").name == "a.mp3"


def test_pick_none_when_empty_or_missing(tmp_path):
    assert pick_track(tmp_path) is None
    assert pick_track(tmp_path / "nahi") is None


def test_mood_from_text():
    assert mood_from_text("shocking war danger") == "dramatic"
    assert mood_from_text("hidden mystery unknown") == "mysterious"
    assert mood_from_text("") == "calm"
