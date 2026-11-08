import pytest

from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard, estimate_duration


def draft(*scenes):
    return ScriptDraft(title=" Space Facts ", hook=" Wow ", scenes=list(scenes))


def test_estimate_duration_scales_with_words():
    assert estimate_duration(" ".join(["word"] * 25)) == 10.0


def test_estimate_duration_has_minimum():
    assert estimate_duration("Hi") == 2.0


def test_build_storyboard_numbers_scenes_and_totals():
    board = build_storyboard(
        draft(
            SceneDraft(narration=" ".join(["a"] * 10), visual_description="x", search_query="galaxy"),
            SceneDraft(narration=" ".join(["b"] * 5), visual_description="y", search_query="stars"),
        )
    )
    assert [s.number for s in board.scenes] == [1, 2]
    assert board.title == "Space Facts"
    assert board.hook == "Wow"
    assert board.total_duration == 6.0
    assert board.full_narration.startswith("a a a")


def test_build_storyboard_skips_empty_narration_and_fills_query():
    board = build_storyboard(
        draft(
            SceneDraft(narration="   ", visual_description="x", search_query="skip"),
            SceneDraft(narration="Real line here", visual_description="y", search_query="  "),
        )
    )
    assert len(board.scenes) == 1
    assert board.scenes[0].number == 1
    assert board.scenes[0].search_query == "Space Facts"


def test_build_storyboard_rejects_empty_script():
    with pytest.raises(ValueError):
        build_storyboard(draft())
