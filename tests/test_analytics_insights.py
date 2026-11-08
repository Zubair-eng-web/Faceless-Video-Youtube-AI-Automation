import pytest

from app.agents.insights_agent import MIN_VIDEOS, Insights, generate_insights
from app.core.analytics import engagement_rate, summarize


def video(id_, views, likes=0, comments=0):
    return {"id": id_, "title": f"Video {id_}", "topic": f"Topic {id_}", "views": views,
            "likes": likes, "comments": comments}


class FakeClient:
    def __init__(self):
        self.calls = []

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.calls.append((prompt, schema, system))
        return Insights(summary="ok", what_works=["a"], what_to_improve=["b"], next_topics=["c"])


def test_engagement_rate():
    assert engagement_rate(100, 8, 2) == 0.1
    assert engagement_rate(0, 5, 5) == 0.0


def test_summarize_empty_or_without_stats():
    empty = {"videos": 0, "total_views": 0, "avg_views": 0, "engagement": 0.0, "best": None}
    assert summarize([]) == empty
    assert summarize([video(1, None)]) == empty


def test_summarize_totals_and_best():
    result = summarize([video(1, 100, 8, 2), video(2, 300, 12, 8), video(3, None)])
    assert result["videos"] == 2
    assert result["total_views"] == 400
    assert result["avg_views"] == 200.0
    assert result["engagement"] == round(30 / 400, 4)
    assert result["best"] == {"id": 2, "title": "Video 2", "views": 300}


def test_generate_insights_needs_enough_videos():
    with pytest.raises(ValueError, match=str(MIN_VIDEOS)):
        generate_insights([video(1, 10), video(2, None)], FakeClient())


def test_generate_insights_prompt_and_result():
    client = FakeClient()
    result = generate_insights([video(1, 10), video(2, 300), video(3, 50)], client)
    prompt, schema, _ = client.calls[0]
    assert "Video 2" in prompt and "300" in prompt
    assert schema is Insights
    assert result.next_topics == ["c"]
