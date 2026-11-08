from types import SimpleNamespace as NS

from app.services.long_package import build_description, chapter_timestamps, fmt_ts, normalize_long_hashtags


def _vo(n=7, step=20.0):
    return NS(scenes=[NS(number=i, start_offset=(i - 1) * step, duration=step) for i in range(1, n + 1)])


CH = [NS(title="A", last_scene=2), NS(title="B", last_scene=4), NS(title="C", last_scene=6), NS(title="D", last_scene=7)]


def test_chapter_timestamps_rules():
    got = chapter_timestamps(CH, _vo(), 140.0)
    assert [fmt_ts(t) for t, _ in got] == ["0:00", "0:40", "1:20", "2:00"]
    assert len(chapter_timestamps(CH, _vo(), 125.0)) == 3  # aakhri chapter 10s se chhota, hat gaya
    assert chapter_timestamps(CH[:2], _vo(4), 80.0) == []  # 3 se kam
    assert fmt_ts(3725) == "1:02:05"


def test_description_keeps_tail_within_limit():
    ch = [(0.0, "A"), (40.0, "B"), (80.0, "C")]
    d = build_description("x" * 6000, ch, "Stock footage: Pixabay", ["#space"])
    assert len(d) <= 5000 and "0:00 A" in d and "Stock footage" in d and d.endswith("#space")


def test_hashtags_dedupe_no_shorts():
    assert normalize_long_hashtags(["Space", "#space", "Black Holes!"]) == ["#Space", "#BlackHoles"]
