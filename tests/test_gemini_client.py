from types import SimpleNamespace

import pytest

from app.core.models import TopicList
from app.services.gemini_client import FENCE, GeminiClient, GeminiError

GOOD = '{"topics": [{"title": "A", "angle": "B", "why_trending": "C"}]}'


class FakeError(Exception):
    def __init__(self, code):
        super().__init__(f"error {code}")
        self.code = code


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(text=item)


class FakeSDK:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def make(responses, sleeps, max_attempts=3):
    return GeminiClient(client=FakeSDK(responses), max_attempts=max_attempts, base_delay=5.0, sleep=sleeps.append)


def test_parses_json_into_model():
    result = make([GOOD], []).generate_json("p", TopicList)
    assert result.topics[0].title == "A"


def test_strips_code_fences():
    fenced = FENCE + "json\n" + GOOD + "\n" + FENCE
    result = make([fenced], []).generate_json("p", TopicList)
    assert result.topics[0].angle == "B"


def test_retries_then_succeeds():
    sleeps = []
    client = make([RuntimeError("boom"), GOOD], sleeps)
    assert client.generate_json("p", TopicList).topics[0].title == "A"
    assert client._client.models.calls == 2
    assert sleeps == [5.0]


def test_gives_up_after_max_attempts():
    sleeps = []
    client = make([RuntimeError("1"), RuntimeError("2"), RuntimeError("3")], sleeps)
    with pytest.raises(GeminiError):
        client.generate_json("p", TopicList)
    assert client._client.models.calls == 3
    assert len(sleeps) == 2


def test_does_not_retry_client_errors():
    sleeps = []
    client = make([FakeError(403), GOOD], sleeps)
    with pytest.raises(GeminiError):
        client.generate_json("p", TopicList)
    assert client._client.models.calls == 1
    assert sleeps == []
