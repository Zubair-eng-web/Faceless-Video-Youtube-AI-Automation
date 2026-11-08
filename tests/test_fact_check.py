from app.core.models import Scene, Storyboard
from app.services.fact_check import build_prompt, check_board


def _board():
    return Storyboard(title="Space", hook="h", language="English", scenes=[
        Scene(number=1, narration="The Sun is a star near Earth today", visual_description="v", search_query="sun", duration=3),
        Scene(number=2, narration="Venus is the closest planet to the Sun", visual_description="v", search_query="venus", duration=3),
    ])


def _ask(claims):
    return lambda prompt: {"claims": claims}


def test_prompt_has_scenes_and_language():
    p = build_prompt(_board())
    assert "Scene 1:" in p and "Scene 2:" in p and "English" in p


def test_wrong_scene_is_fixed():
    claims = [
        {"scene_number": 1, "claim": "Sun is a star", "verdict": "ok"},
        {"scene_number": 2, "claim": "Venus closest", "verdict": "wrong", "reason": "Mercury is",
         "fixed_narration": "Mercury is the closest planet to the Sun"},
    ]
    b, r = check_board(_board(), _ask(claims))
    assert b.scenes[1].narration.startswith("Mercury")
    assert b.scenes[0].narration.startswith("The Sun")
    assert r.fixed_scenes == [2] and len(r.wrong) == 1


def test_no_fix_when_auto_fix_off():
    claims = [{"scene_number": 2, "claim": "x", "verdict": "wrong", "fixed_narration": "Mercury is the closest planet to the Sun"}]
    b, r = check_board(_board(), _ask(claims), auto_fix=False)
    assert b.scenes[1].narration.startswith("Venus") and r.fixed_scenes == []


def test_bad_length_fix_is_ignored():
    claims = [{"scene_number": 2, "claim": "x", "verdict": "wrong", "fixed_narration": "No."}]
    b, r = check_board(_board(), _ask(claims))
    assert b.scenes[1].narration.startswith("Venus") and r.fixed_scenes == []


def test_doubtful_never_changes_text():
    claims = [{"scene_number": 1, "claim": "x", "verdict": "doubtful", "fixed_narration": "Something else entirely different here now"}]
    b, r = check_board(_board(), _ask(claims))
    assert b == _board() and len(r.doubtful) == 1


def test_invalid_items_and_unknown_scene_skipped():
    claims = [{"scene_number": 9, "claim": "x", "verdict": "wrong"}, {"junk": 1},
              {"scene_number": 1, "claim": "ok", "verdict": "ok"}]
    _, r = check_board(_board(), _ask(claims))
    assert len(r.claims) == 1


def test_gemini_error_does_not_break():
    def boom(prompt):
        raise RuntimeError("429")
    b, r = check_board(_board(), boom)
    assert b == _board() and r.checked is False and "429" in r.summary()
