import pytest

from app.agents.research_agent import suggest_topics
from app.agents.script_agent import SYSTEM_PROMPT, generate_script
from app.core.models import SceneDraft, ScriptDraft, TopicIdea, TopicList


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.calls.append((prompt, schema, system))
        return self.result


def topic(title):
    return TopicIdea(title=title, angle="angle", why_trending="why")


def test_suggest_topics_drops_blank_and_limits_count():
    client = FakeClient(TopicList(topics=[topic("A"), topic("  "), topic("B"), topic("C")]))
    result = suggest_topics("space", client, count=2)
    assert [t.title for t in result] == ["A", "B"]
    assert "space" in client.calls[0][0]


def test_suggest_topics_rejects_empty_niche():
    with pytest.raises(ValueError):
        suggest_topics("   ", FakeClient(TopicList(topics=[])))


def fake_draft():
    return ScriptDraft(
        title="Black Holes",
        hook="What if time stopped?",
        scenes=[
            SceneDraft(narration="What if time stopped?", visual_description="space", search_query="black hole space"),
            SceneDraft(narration="Follow for more.", visual_description="stars", search_query="night sky stars"),
        ],
    )


def test_generate_script_returns_storyboard():
    client = FakeClient(fake_draft())
    board = generate_script("Black holes", client, language="Hindi")
    assert board.language == "Hindi"
    assert len(board.scenes) == 2
    assert board.scenes[0].search_query == "black hole space"


def test_generate_script_prompt_has_topic_and_language():
    client = FakeClient(fake_draft())
    generate_script("Black holes", client, language="Hindi", target_seconds=30)
    prompt, schema, _ = client.calls[0]
    assert "Black holes" in prompt
    assert "Hindi" in prompt
    assert "75 words" in prompt
    assert schema is ScriptDraft


def test_generate_script_rejects_empty_topic():
    with pytest.raises(ValueError):
        generate_script("  ", FakeClient(fake_draft()))


def test_system_prompt_asks_for_stock_footage_queries():
    assert "stock footage" in SYSTEM_PROMPT
