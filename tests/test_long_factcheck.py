from app.core.models import Scene, Storyboard
from app.services.fact_check import FactCheckDraft
from app.services.long_factcheck import extract_json, fact_check_long
from app.services.long_script import ChapterInfo, LongScript

WRONG = '{"claims": [{"scene_number": 2, "claim": "Venus closest", "verdict": "wrong", "reason": "Mercury is", "fixed_narration": "Mercury is the closest planet to the Sun"}, {"scene_number": 1, "claim": "Sun is a star", "verdict": "ok"}]}'
OKJSON = '{"claims": [{"scene_number": 3, "claim": "c", "verdict": "ok"}]}'


def _script():
    texts = ["The Sun is a star near Earth today", "Venus is the closest planet to the Sun",
             "Mars is the red planet in our system", "Jupiter is the largest planet in our system"]
    board = Storyboard(title="T", hook="h", language="English", scenes=[
        Scene(number=i + 1, narration=t, visual_description="v", search_query="q", duration=3.0)
        for i, t in enumerate(texts)])
    return LongScript(storyboard=board, chapters=[ChapterInfo(title="A", first_scene=1, last_scene=2, words=16),
                                                  ChapterInfo(title="B", first_scene=3, last_scene=4, words=16)],
                      minutes=1, words=32)


class FakeGemini:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.calls.append(prompt[:30])
        if self.fail:
            raise RuntimeError("429")
        return FactCheckDraft.model_validate({"claims": [{"scene_number": 3, "claim": "c", "verdict": "ok"}]})


def _grounded(replies):
    seen = []

    def fn(prompt):
        seen.append(prompt)
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r, ["Site - http://x"]

    fn.seen = seen
    return fn


def test_extract_json():
    assert extract_json("```json\n" + OKJSON + "\n```")["claims"][0]["scene_number"] == 3
    assert extract_json("no json here") is None and extract_json('{"a": 1}') is None


def test_grounded_fixes_wrong_scene_and_saves(tmp_path):
    g = _grounded([WRONG, OKJSON])
    board, rep = fact_check_long(_script(), FakeGemini(), run_dir=tmp_path, grounded_fn=g, progress=lambda m: None)
    assert board.scenes[1].narration.startswith("Mercury") and board.scenes[0].narration.startswith("The Sun")
    assert rep.grounded and rep.fixed_scenes == [2] and rep.sources == ["Site - http://x"]
    assert not rep.unresolved_wrong and not rep.needs_review and "Search to verify" in g.seen[0]
    assert (tmp_path / "long_fact_01.json").exists() and (tmp_path / "fact_check.json").exists()
    assert "Mercury" in (tmp_path / "storyboard.json").read_text(encoding="utf-8")
    assert rep.to_fact_report().fixed_scenes == [2]


def test_non_json_reply_is_structured_by_second_call():
    f = FakeGemini()
    _, rep = fact_check_long(_script(), f, grounded_fn=_grounded(["prose only", OKJSON]), progress=lambda m: None)
    assert len(f.calls) == 1 and rep.grounded and len(rep.chapters) == 2


def test_grounding_failure_falls_back_for_rest():
    f = FakeGemini()
    g = _grounded([RuntimeError("400 tool not supported")])
    _, rep = fact_check_long(_script(), f, grounded_fn=g, progress=lambda m: None)
    assert len(g.seen) == 1 and len(f.calls) == 2 and not rep.grounded and rep.needs_review
    assert any("Web search band" in w for w in rep.warnings) and len(rep.chapters) == 2


def test_both_fail_marks_unchecked_and_does_not_save(tmp_path):
    g = _grounded([RuntimeError("x")])
    _, rep = fact_check_long(_script(), FakeGemini(fail=True), run_dir=tmp_path, grounded_fn=g,
                             progress=lambda m: None)
    assert rep.unchecked == ["A", "B"] and rep.needs_review and not list(tmp_path.glob("long_fact_0*.json"))
    assert rep.to_fact_report().checked is False


def test_resume_makes_no_calls(tmp_path):
    fact_check_long(_script(), FakeGemini(), run_dir=tmp_path, grounded_fn=_grounded([WRONG, OKJSON]),
                    progress=lambda m: None)
    f, g = FakeGemini(), _grounded([])
    board, rep = fact_check_long(_script(), f, run_dir=tmp_path, grounded_fn=g, progress=lambda m: None)
    assert f.calls == [] and g.seen == [] and board.scenes[1].narration.startswith("Mercury")


def test_autofix_off_keeps_text_but_flags_wrong():
    board, rep = fact_check_long(_script(), FakeGemini(), grounded_fn=_grounded([WRONG, OKJSON]), auto_fix=False,
                                 progress=lambda m: None)
    assert board.scenes[1].narration.startswith("Venus") and len(rep.unresolved_wrong) == 1 and rep.needs_review


def test_grounded_disabled_by_setting():
    f = FakeGemini()
    g = _grounded([])
    _, rep = fact_check_long(_script(), f, grounded_fn=g, grounded=False, progress=lambda m: None)
    assert g.seen == [] and len(f.calls) == 2 and not rep.grounded
