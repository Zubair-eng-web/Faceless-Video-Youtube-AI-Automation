"""Task 25+26: research, script mein facts, aur script validation (asli API nahi, sab fake)."""
import json

from app.core.models import Scene, Storyboard
from app.services.long_research import (ChapterResearch, ResearchDraft, ResearchFact, ResearchFactDraft,
                                        ChapterResearchDraft, ResearchReport, research_long)
from app.services.long_script import (ChapterDraft, ChapterInfo, ChapterPlan, LongConfig, LongScript, Outline,
                                      SeriesStyle, chapter_prompt, generate_long_script)
from app.services.long_validation import validate_script


def make_outline(n=4):
    return Outline(title="T", hook="Hook here.",
                   chapters=[ChapterPlan(title=f"C{i}", summary="s", key_points=["a"]) for i in range(n)])


GOOD_JSON = json.dumps({"chapters": [
    {"chapter": 1, "facts": [{"fact": "Fact one.", "source": "NASA"}]},
    {"chapter": 2, "facts": [{"fact": "Fact two.", "source": "ESA"}, {"fact": "Fact two.", "source": "ESA"}]},
]})


class FakeGemini:
    def __init__(self):
        self.calls = 0

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.calls += 1
        return ResearchDraft(chapters=[ChapterResearchDraft(
            chapter=1, facts=[ResearchFactDraft(fact="Plain fact.", source="Wiki")])])


def test_research_grounded_saves_and_resumes(tmp_path):
    calls = []

    def grounded(prompt):
        calls.append(prompt)
        return GOOD_JSON, ["NASA - https://nasa.gov/x"]

    g = FakeGemini()
    rep = research_long("Mars", make_outline(), g, run_dir=tmp_path, grounded_fn=grounded, grounded=True,
                        progress=lambda m: None)
    assert rep.grounded and rep.sources == ["NASA - https://nasa.gov/x"]
    assert rep.facts_for(0) == ["Fact one. (source: NASA)"]
    assert rep.facts_for(1) == ["Fact two. (source: ESA)"]  # dohra fact hat gaya
    assert rep.facts_for(3) == []
    assert any("Chapter 3" in w for w in rep.warnings)
    assert (tmp_path / "long_research.json").exists()
    again = research_long("Mars", make_outline(), g, run_dir=tmp_path, grounded_fn=grounded, grounded=True,
                          progress=lambda m: None)
    assert len(calls) == 1 and again.total_facts == rep.total_facts


def test_research_falls_back_when_grounding_fails():
    def grounded(prompt):
        raise RuntimeError("quota")

    rep = research_long("Mars", make_outline(), FakeGemini(), grounded_fn=grounded, grounded=True,
                        progress=lambda m: None)
    assert not rep.grounded and rep.facts_for(0) == ["Plain fact. (source: Wiki)"]
    assert any("fail" in w for w in rep.warnings)


def test_research_converts_non_json_answer():
    g = FakeGemini()
    rep = research_long("Mars", make_outline(), g, grounded_fn=lambda p: ("not json at all", ["a - https://a.com"]),
                        grounded=True, progress=lambda m: None)
    assert rep.grounded and g.calls == 1 and rep.total_facts == 1


def test_research_never_raises():
    class Broken:
        def generate_json(self, *a, **k):
            raise RuntimeError("down")

    rep = research_long("Mars", make_outline(), Broken(), grounded=False, progress=lambda m: None)
    assert rep.total_facts == 0 and rep.warnings


def test_chapter_prompt_includes_facts():
    o = make_outline()
    with_facts = chapter_prompt("Mars", "English", SeriesStyle(), o, 0, 100, 6, "", facts=["Fact A (source: X)"])
    without = chapter_prompt("Mars", "English", SeriesStyle(), o, 0, 100, 6, "")
    assert "Verified research facts" in with_facts and "Fact A (source: X)" in with_facts
    assert "Verified research facts" not in without


class FakeClient:
    def __init__(self):
        self.prompts = []

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.prompts.append(prompt)
        if schema is Outline:
            return make_outline(4)
        from app.core.models import SceneDraft
        text = "Alpha beta gamma delta epsilon zeta eta theta iota kappa. " * 10
        return ChapterDraft(scenes=[SceneDraft(narration=text, visual_description="v", search_query="sky")])


def test_generate_long_script_passes_facts_to_chapters():
    client = FakeClient()
    report = ResearchReport(topic="x", chapters=[
        ChapterResearch(index=i + 1, facts=[ResearchFact(fact=f"UniqueFact{i}", source="S")]) for i in range(4)])
    result = generate_long_script("Mars", client, minutes=3, cfg=LongConfig(), progress=lambda m: None,
                                  researcher=lambda outline: report)
    assert len(result.chapters) == 4
    for i in range(4):
        assert any(f"UniqueFact{i}" in p for p in client.prompts)


def test_generate_long_script_without_researcher_unchanged():
    client = FakeClient()
    generate_long_script("Mars", client, minutes=3, cfg=LongConfig(), progress=lambda m: None)
    assert not any("Verified research facts" in p for p in client.prompts)


def make_script(minutes=10, n_scenes=100, words=15, n_chapters=5):
    scenes = []
    for i in range(n_scenes):
        text = " ".join(f"w{i}x{j}" for j in range(words))
        if i == 0:
            text = "Hook words here now " + text
        scenes.append(Scene(number=i + 1, narration=text, visual_description="v", search_query=f"q{i}",
                            duration=round(words / 2.5, 2)))
    per = n_scenes // n_chapters
    chapters = []
    for c in range(n_chapters):
        first, last = c * per + 1, (c + 1) * per if c < n_chapters - 1 else n_scenes
        w = sum(len(s.narration.split()) for s in scenes[first - 1:last])
        chapters.append(ChapterInfo(title=f"C{c}", first_scene=first, last_scene=last, words=w))
    board = Storyboard(title="T", hook="Hook words here now", scenes=scenes)
    return LongScript(storyboard=board, chapters=chapters, minutes=minutes,
                      words=sum(c.words for c in chapters))


def test_validation_good_script_has_no_issues():
    rep = validate_script(make_script(), LongConfig())
    assert rep.ok and not rep.issues


def test_validation_too_short_is_error():
    rep = validate_script(make_script(n_scenes=20), LongConfig())
    assert not rep.ok and rep.errors


def test_validation_few_scenes_is_warning():
    rep = validate_script(make_script(n_scenes=60, words=25), LongConfig())
    assert rep.ok and any("Scenes 80-150" in i.message for i in rep.warnings)


def test_validation_detects_duplicate_narration():
    s = make_script()
    s.storyboard.scenes[5] = s.storyboard.scenes[4].model_copy(update={"number": 6})
    rep = validate_script(s, LongConfig())
    assert any("dohra" in i.message for i in rep.warnings)