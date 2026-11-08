from types import SimpleNamespace as NS

from app.services.long_render import chunk_filter, chunk_words, plan_chunks


def test_plan_chunks_respects_chapters_and_splits_big_ones():
    assert plan_chunks(30, [10, 20], 20) == [(0, 10), (10, 20), (20, 30)]
    assert plan_chunks(45, [45], 20) == [(0, 15), (15, 30), (30, 45)]
    assert plan_chunks(0, []) == []


def test_chunk_words_shift_and_filter():
    words = [NS(start=s, end=s + 0.5, model_copy=None) for s in (1.0, 11.0)]
    class W:
        def __init__(self, s, e): self.start, self.end = s, e
        def model_copy(self, update): return W(update["start"], update["end"])
    got = chunk_words([W(1.0, 1.5), W(11.0, 11.5)], 10.0, 20.0)
    assert len(got) == 1 and got[0].start == 1.0 and got[0].end == 1.5


def test_chunk_filter_chain():
    fc = chunk_filter([5, 5, 5], 0.4, True, "cap_001.ass")
    assert fc.count("xfade") == 2 and "offset=10.000" in fc
    assert fc.endswith("ass=cap_001.ass:fontsdir=fonts[vout]")
    assert chunk_filter([5], 0.4, False, "c.ass") == "[0:v]ass=c.ass[vout]"
