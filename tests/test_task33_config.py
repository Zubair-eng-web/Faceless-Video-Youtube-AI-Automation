"""Task 33: configurable provider, limits aur throttle (asli API nahi, sab fake)."""
import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.services import gemini_client as gc
from app.services.gemini_client import GeminiClient, GeminiError, make_gemini_client


class Answer(BaseModel):
    value: str


class FakeResponse:
    text = '{"value": "ok"}'


class FakeModels:
    def __init__(self, fail_times=0):
        self.calls = 0
        self.fail_times = fail_times

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("temporary")
        return FakeResponse()


class FakeSdk:
    def __init__(self, fail_times=0):
        self.models = FakeModels(fail_times)


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.ai_provider == "gemini"
    assert s.gemini_max_attempts == 4
    assert s.gemini_min_interval_seconds == 0.0
    assert (s.long_video_width, s.long_video_height) == (1920, 1080)
    assert (s.video_width, s.video_height) == (1080, 1920)  # Shorts wahi rahe


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "Gemini")
    monkeypatch.setenv("GEMINI_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("GEMINI_MIN_INTERVAL_SECONDS", "4")
    s = Settings(_env_file=None)
    assert s.ai_provider == "Gemini"
    assert s.gemini_max_attempts == 2
    assert s.gemini_min_interval_seconds == 4.0


def test_client_uses_settings_defaults(monkeypatch):
    monkeypatch.setattr(gc.settings, "gemini_max_attempts", 3)
    monkeypatch.setattr(gc.settings, "gemini_retry_delay", 1.5)
    c = GeminiClient(client=FakeSdk())
    assert c.max_attempts == 3
    assert c.base_delay == 1.5


def test_explicit_args_override_settings():
    c = GeminiClient(client=FakeSdk(), max_attempts=7, base_delay=0.1, min_interval=2)
    assert (c.max_attempts, c.base_delay, c.min_interval) == (7, 0.1, 2)


def test_retry_then_success_counts_requests():
    sleeps = []
    c = GeminiClient(client=FakeSdk(fail_times=1), max_attempts=3, base_delay=2, sleep=sleeps.append, min_interval=0)
    assert c.generate_json("hi", Answer).value == "ok"
    assert c.requests_made == 2
    assert sleeps == [2]


def test_throttle_waits_between_requests():
    sleeps = []
    c = GeminiClient(client=FakeSdk(), sleep=sleeps.append, min_interval=4, clock=lambda: 100.0)
    c.generate_json("a", Answer)
    assert sleeps == []  # pehli request par intezar nahi
    c.generate_json("b", Answer)
    assert sleeps == [4]
    assert c.requests_made == 2


def test_no_throttle_when_interval_zero():
    sleeps = []
    c = GeminiClient(client=FakeSdk(), sleep=sleeps.append, min_interval=0, clock=lambda: 100.0)
    c.generate_json("a", Answer)
    c.generate_json("b", Answer)
    assert sleeps == []


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setattr(gc.settings, "ai_provider", "openai")
    with pytest.raises(GeminiError):
        make_gemini_client()


def test_factory_builds_gemini_client(monkeypatch):
    monkeypatch.setattr(gc.settings, "ai_provider", "gemini")
    monkeypatch.setattr(gc.settings, "gemini_api_key", "test-key-123")
    monkeypatch.setattr(gc.genai, "Client", lambda api_key=None: FakeSdk())
    c = make_gemini_client(model="my-model")
    assert isinstance(c, GeminiClient)
    assert c.model == "my-model"