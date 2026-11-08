from pathlib import Path

import pytest

from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard
from app.services.tts import (
    TTSError,
    WordTiming,
    apply_durations,
    fallback_word_timings,
    generate_voiceover,
    pick_voice,
    shift_words,
    ticks_to_seconds,
)


def make_board():
    return build_storyboard(
        ScriptDraft(
            title="T",
            hook="h",
            scenes=[
                SceneDraft(narration="one two three", visual_description="v", search_query="q"),
                SceneDraft(narration="four five", visual_description="v", search_query="q"),
            ],
        )
    )


DURATIONS = {"scene_01.mp3": 3.0, "scene_02.mp3": 2.0}


def fake_duration(path):
    return DURATIONS[Path(path).name]


def fake_concat(paths, out):
    Path(out).write_bytes(b"joined")


async def fake_synth(text, voice, rate, path):
    Path(path).write_bytes(b"audio")
    if text.startswith("one"):
        return [WordTiming(text="one", start=0.0, end=1.0), WordTiming(text="two", start=1.0, end=3.0)]
    return []  # doosre scene me word events nahi: fallback chalna chahiye


def test_ticks_to_seconds():
    assert ticks_to_seconds(10_000_000) == 1.0
    assert ticks_to_seconds(5_000_000) == 0.5


def test_shift_words_adds_offset():
    shifted = shift_words([WordTiming(text="a", start=0.5, end=1.0)], 2.0)
    assert (shifted[0].start, shifted[0].end) == (2.5, 3.0)


def test_fallback_timings_cover_whole_duration():
    words = fallback_word_timings("aa bbbb", 6.0)
    assert [w.text for w in words] == ["aa", "bbbb"]
    assert words[0].start == 0.0
    assert words[0].end == words[1].start == 2.25
    assert words[1].end == 6.0


def test_pick_voice_by_language():
    assert pick_voice("english") == "en-US-AndrewNeural"
    assert pick_voice("Hindi") == "hi-IN-MadhurNeural"


def test_pick_voice_override_wins():
    assert pick_voice("English", "en-US-AriaNeural") == "en-US-AriaNeural"


def test_pick_voice_unknown_language():
    with pytest.raises(ValueError):
        pick_voice("Klingon")


def test_generate_voiceover_offsets_and_fallback(tmp_path):
    vo = generate_voiceover(make_board(), tmp_path, synth=fake_synth, duration_fn=fake_duration, concat_fn=fake_concat)
    assert vo.voice == "en-US-AndrewNeural"
    assert vo.duration == 5.0
    assert [s.start_offset for s in vo.scenes] == [0.0, 3.0]
    assert Path(vo.path).name == "voiceover.mp3"
    words = vo.words
    assert [w.text for w in words] == ["one", "two", "four", "five"]
    assert words[2].start == 3.0
    assert words[-1].end == 5.0


def test_generate_voiceover_retries_then_succeeds(tmp_path):
    state = {"calls": 0}
    sleeps = []

    async def flaky(text, voice, rate, path):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("network")
        return await fake_synth(text, voice, rate, path)

    generate_voiceover(make_board(), tmp_path, synth=flaky, duration_fn=fake_duration,
                       concat_fn=fake_concat, sleep=sleeps.append)
    assert state["calls"] == 3  # pehle scene me 2, doosre me 1
    assert sleeps == [2.0]


def test_generate_voiceover_gives_up(tmp_path):
    async def always_fail(text, voice, rate, path):
        raise RuntimeError("down")

    with pytest.raises(TTSError):
        generate_voiceover(make_board(), tmp_path, synth=always_fail, duration_fn=fake_duration,
                           concat_fn=fake_concat, max_attempts=2, sleep=lambda s: None)


def test_apply_durations_uses_real_values(tmp_path):
    board = make_board()
    vo = generate_voiceover(board, tmp_path, synth=fake_synth, duration_fn=fake_duration, concat_fn=fake_concat)
    updated = apply_durations(board, vo)
    assert [s.duration for s in updated.scenes] == [3.0, 2.0]
    assert updated.total_duration == 5.0
