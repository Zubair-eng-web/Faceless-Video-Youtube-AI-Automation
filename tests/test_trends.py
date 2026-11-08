import json

from app.agents.research_agent import suggest_topics
from app.core.models import TopicIdea, TopicList
from app.services.trends import (any_connected_channel, fetch_trending, fetch_with_fallback, niche_category,
                                 region_for_language, trend_titles)


class Call:
    def __init__(self, r):
        self.r = r

    def execute(self):
        if isinstance(self.r, Exception):
            raise self.r
        return self.r


class FakeService:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def videos(self):
        return self

    def list(self, **kw):
        self.calls.append(kw)
        return Call(self.responses.pop(0))


def _resp(*titles):
    return {"items": [{"snippet": {"title": t, "channelTitle": "C", "categoryId": "28"},
                       "statistics": {"viewCount": "100"}} for t in titles]}


def test_niche_category_and_region(monkeypatch):
    assert niche_category("space facts") == "28"
    assert niche_category("Gaming tips") == "20"
    assert niche_category("kuch aur") is None
    monkeypatch.delenv("TRENDS_REGION", raising=False)
    assert region_for_language("Urdu") == "PK" and region_for_language("English") == "US"
    assert region_for_language("Klingon") == "US"
    monkeypatch.setenv("TRENDS_REGION", "gb")
    assert region_for_language("Urdu") == "GB"


def test_fetch_trending_cleans_and_dedupes():
    s = FakeService([_resp("  Black   hole  ", "black hole", "", "Mars")])
    items = fetch_trending(s, "US", "28")
    assert [i.title for i in items] == ["Black hole", "Mars"] and items[0].views == 100
    assert s.calls[0]["chart"] == "mostPopular" and s.calls[0]["videoCategoryId"] == "28"


def test_fetch_error_returns_empty():
    assert fetch_trending(FakeService([RuntimeError("quota")])) == []


def test_fallback_to_general_when_category_fails():
    s = FakeService([RuntimeError("400"), _resp("General")])
    items = fetch_with_fallback(s, "US", "28")
    assert [i.title for i in items] == ["General"] and "videoCategoryId" not in s.calls[1]


def test_trend_titles_limit_and_failures(tmp_path):
    s = FakeService([_resp("A", "B", "C")])
    assert trend_titles("space", "English", limit=2, service=s) == ["A", "B"]
    assert trend_titles("space", tokens_dir=tmp_path) == []  # token nahi


def test_any_connected_channel(tmp_path):
    assert any_connected_channel(tmp_path / "nahi") is None
    (tmp_path / "youtube_3.json").write_text(json.dumps({}), encoding="utf-8")
    assert any_connected_channel(tmp_path) == "3"


class FakeGemini:
    def __init__(self):
        self.prompt = None

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.prompt = prompt
        return TopicList(topics=[TopicIdea(title="T", angle="a", why_trending="w")])


def test_suggest_topics_with_and_without_trends():
    g = FakeGemini()
    suggest_topics("space", g)
    assert "Currently popular" not in g.prompt
    suggest_topics("space", g, trends=["Black hole news", "Mars"])
    assert "Currently popular" in g.prompt and "- Black hole news" in g.prompt
