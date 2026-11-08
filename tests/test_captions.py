from app.services.captions import build_ass, fmt_time, group_words
from app.services.tts import WordTiming


def w(text, start, end):
    return WordTiming(text=text, start=start, end=end)


def test_fmt_time():
    assert fmt_time(0) == "0:00:00.00"
    assert fmt_time(61.5) == "0:01:01.50"
    assert fmt_time(3725.256) == "1:02:05.26"


def test_group_words_splits_on_sentence_end_and_max_words():
    words = [w("Hello", 0, 1), w("world.", 1, 2), w("This", 2, 3), w("is", 3, 4), w("a", 4, 5), w("test", 5, 6)]
    groups = group_words(words, max_words=3)
    assert [len(g) for g in groups] == [2, 3, 1]


def test_group_words_splits_on_max_chars():
    words = [w("aaaaaa", 0, 1), w("bbbbbb", 1, 2), w("cccccc", 2, 3)]
    groups = group_words(words, max_words=3, max_chars=18)
    assert [len(g) for g in groups] == [2, 1]


def test_build_ass_has_header_and_one_line_per_word():
    words = [w("a", 0.0, 0.5), w("b", 0.6, 1.0), w("c", 1.1, 1.5), w("d", 1.6, 2.0)]
    ass = build_ass(words)
    assert "PlayResX: 1080" in ass
    assert "PlayResY: 1920" in ass
    assert ass.count("Dialogue:") == 4


def test_build_ass_highlights_current_word():
    words = [w("a", 0.0, 0.5), w("b", 0.6, 1.0), w("c", 1.1, 1.5), w("d", 1.6, 2.0)]
    first = [line for line in build_ass(words).splitlines() if line.startswith("Dialogue:")][0]
    assert "{\\c&H00FFFF&}A{\\c&HFFFFFF&} B C" in first
    assert "0:00:00.00,0:00:00.60" in first  # pehla lafz agle lafz ke start tak dikhta hai


def test_build_ass_escapes_braces():
    ass = build_ass([w("{hi}", 0.0, 1.0)])
    assert "(HI)" in ass


def test_build_ass_with_no_words_has_no_dialogue():
    assert "Dialogue:" not in build_ass([])
