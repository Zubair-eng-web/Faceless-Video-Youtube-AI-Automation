from types import SimpleNamespace

from app.core.models import Scene, Storyboard
from app.services.fact_check import FactCheckDraft, FactCheckReport, ClaimCheck, run_fact_check


def _board():
    return Storyboard(title="t", hook="h", language="English", scenes=[
        Scene(number=1, narration="Venus is the closest planet to the Sun", visual_description="v", search_query="q", duration=3),
    ])


class FakeGemini:
    def __init__(self, draft=None, error=None):
        self.draft, self.error, self.seen = draft, error, None

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.seen = schema
        if self.error:
            raise self.error
        return self.draft


def test_run_fact_check_uses_schema_and_fixes():
    draft = FactCheckDraft(claims=[ClaimCheck(scene_number=1, claim="c", verdict="wrong",
                                              fixed_narration="Mercury is the closest planet to the Sun")])
    g = FakeGemini(draft)
    b, r = run_fact_check(_board(), g)
    assert g.seen is FactCheckDraft and b.scenes[0].narration.startswith("Mercury")
    assert r.fixed_scenes == [1] and r.unresolved_wrong == []


def test_unfixable_wrong_is_unresolved():
    draft = FactCheckDraft(claims=[ClaimCheck(scene_number=1, claim="c", verdict="wrong", fixed_narration="No.")])
    _, r = run_fact_check(_board(), FakeGemini(draft))
    assert len(r.unresolved_wrong) == 1


def test_gemini_error_is_safe():
    b, r = run_fact_check(_board(), FakeGemini(error=RuntimeError("429")))
    assert b == _board() and r.checked is False and r.unresolved_wrong == []
