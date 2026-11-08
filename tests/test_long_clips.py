from types import SimpleNamespace

import pytest

from app.core.models import Scene, Storyboard
from app.services.long_clips import collect_long_clips, long_query_options, pick_long, score_long
from app.services.pixabay import PixabayError


def C(i, w=1920, h=1080, d=15.0):
    return SimpleNamespace(id=i, width=w, height=h, duration=d, page_url="u", is_portrait=h > w)


def _board(n, query=lambda i: f"q{i}"):
    return Storyboard(title="Title", hook="h", language="English", scenes=[
        Scene(number=i, narration="n", visual_description="a b c d e f", search_query=query(i), duration=7.0)
        for i in range(1, n + 1)])


def _dl(c, client, cache_dir=None, sleep=None):
    return f"clip_{c.id}.mp4"


KW = dict(progress=lambda m: None, sleep=lambda s: None, download_fn=_dl)


def test_landscape_preferred_and_used_excluded():
    assert score_long(C(1), 7) > score_long(C(2, 1080, 1920), 7)
    assert pick_long([C(1, 1080, 1920), C(2)], 7, set()).id == 2
    assert pick_long([C(1)], 7, {1}) is None


def test_query_options_dedupe_and_order():
    s = Scene(number=1, narration="n", visual_description="x y z w v", search_query="black hole", duration=7)
    assert long_query_options(s, "Title") == ["black hole", "x y z w", "Title"]


def test_no_clip_repeats_when_enough_candidates():
    search = lambda q, client, **kw: [C(1), C(2), C(3)]
    clips, rep = collect_long_clips(_board(3), None, search_fn=search, **KW)
    assert sorted(c.clip_id for c in clips) == [1, 2, 3] and rep.unique == 3 and rep.reused_scenes == []


def test_reuses_oldest_when_candidates_run_out():
    search = lambda q, client, **kw: [C(1), C(2)]
    clips, rep = collect_long_clips(_board(5), None, search_fn=search, **KW)
    assert len(clips) == 5 and rep.unique == 2 and rep.reused_scenes == [3, 4, 5]
    assert [c.clip_id for c in clips[2:]] == [1, 2, 1] and rep.warnings


def test_falls_back_to_next_query_and_survives_search_error():
    calls = []

    def search(q, client, **kw):
        calls.append(q)
        if q == "q1":
            raise RuntimeError("429")
        return [C(7)]

    clips, _ = collect_long_clips(_board(1), None, search_fn=search, **KW)
    assert clips[0].clip_id == 7 and calls[0] == "q1" and len(calls) == 2


def test_no_clip_at_all_raises():
    with pytest.raises(PixabayError):
        collect_long_clips(_board(1), None, search_fn=lambda q, c, **kw: [], **KW)


def test_resume_skips_existing_files(tmp_path):
    f = tmp_path / "clip_1.mp4"
    f.write_bytes(b"x")
    search = lambda q, client, **kw: [C(1), C(2)]
    dl = lambda c, client, cache_dir=None, sleep=None: str(tmp_path / f"clip_{c.id}.mp4")
    (tmp_path / "clip_2.mp4").write_bytes(b"x")
    collect_long_clips(_board(2), None, run_dir=tmp_path, search_fn=search,
                       progress=lambda m: None, sleep=lambda s: None, download_fn=dl)
    seen = []

    def search2(q, client, **kw):
        seen.append(q)
        return [C(9)]

    clips, rep = collect_long_clips(_board(2), None, run_dir=tmp_path, search_fn=search2,
                                    progress=lambda m: None, sleep=lambda s: None, download_fn=dl)
    assert seen == [] and rep.reused_from_resume == 2 and [c.clip_id for c in clips] == [1, 2]
