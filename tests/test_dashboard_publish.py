import json
from datetime import date, time
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

from app.core.config import Settings
from dashboard.api_client import ApiClient, ApiError
from dashboard.helpers import (
    STATUSES,
    can_publish,
    can_retry_publish,
    combine_when,
    is_active,
    schedule_text,
    status_label,
    youtube_link,
)

APP_FILE = Path(__file__).resolve().parents[1] / "dashboard" / "streamlit_app.py"


def test_new_statuses_have_labels():
    for status in ("publishing", "published", "publish_failed"):
        assert status in STATUSES
        assert status_label(status) != status


def test_publish_rules():
    assert can_publish("approved")
    assert not can_publish("ready") and not can_publish("published")
    assert can_retry_publish("publish_failed")
    assert not can_retry_publish("approved")


def test_publishing_counts_as_active():
    assert is_active({"status": "publishing"})


def test_schedule_text():
    assert schedule_text({"scheduled_at": "2026-11-07T10:00:00"}) == "2026-11-07 10:00"
    assert schedule_text({}) is None


def test_youtube_link():
    assert youtube_link({"youtube_id": "abc"}) == "https://www.youtube.com/watch?v=abc"
    assert youtube_link({"youtube_id": None}) is None


def test_combine_when():
    assert combine_when(date(2026, 11, 7), time(10, 30, 45)) == "2026-11-07T10:30:00"


def test_client_publishing_calls():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.content))
        return httpx.Response(200, json={})

    client = ApiClient("http://api.test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    client.publish(3)
    client.schedule(3, "2026-11-07T10:00:00")
    client.unschedule(3)
    client.retry_publish(3)
    client.publishing_info()
    client.youtube_channels()
    assert [(m, p) for m, p, _ in seen] == [
        ("POST", "/videos/3/publish"),
        ("POST", "/videos/3/schedule"),
        ("POST", "/videos/3/unschedule"),
        ("POST", "/videos/3/retry-publish"),
        ("GET", "/publishing"),
        ("GET", "/youtube/channels"),
    ]
    assert json.loads(seen[1][2]) == {"when": "2026-11-07T10:00:00"}


def test_settings_publish_defaults():
    s = Settings(_env_file=None)
    assert s.auto_publish is False
    assert s.default_privacy == "private"
    assert s.daily_upload_limit == 5
    assert s.publish_check_minutes == 5


# ---------- Streamlit smoke tests ----------
class Resp:
    def __init__(self, data=None):
        self._data = data

    def json(self):
        return self._data


def make_video(status, **extra):
    video = {
        "id": 1, "channel_id": 1, "topic": "Moon", "language": "English", "status": status,
        "title": "Moon Silence", "duration": 20.5, "error": None, "run_dir": "r",
        "created_at": "2026-11-06T09:00:00", "updated_at": "2026-11-06T09:00:03",
        "seo": {"title": "Moon Silence", "description": "Desc", "hashtags": ["#Shorts"], "tags": ["moon"],
                "thumbnail_text": "THE MOON"},
        "quality": {"issues": [], "stats": {}},
    }
    video.update(extra)
    return video


def run_app(monkeypatch, video, connected=True):
    channel = {"id": 1, "name": "Space", "niche": "space", "language": "English", "voice": None,
               "created_at": "2026-11-06T09:00:00"}

    def fake(self, method, path, **kwargs):
        if path == "/health":
            return Resp({"status": "ok"})
        if path == "/stats":
            return Resp({"total": 1})
        if path == "/channels":
            return Resp([channel])
        if path == "/videos":
            return Resp([video])
        if path == "/videos/1":
            return Resp(video)
        if path == "/youtube/channels":
            return Resp([{"id": 1, "name": "Space", "connected": connected}])
        raise ApiError("fake: " + path)

    monkeypatch.setattr(ApiClient, "_request", fake)
    app = AppTest.from_file(str(APP_FILE), default_timeout=20)
    app.run()
    assert not app.exception
    return app


def test_panel_hints_to_connect_when_channel_is_not_connected(monkeypatch):
    app = run_app(monkeypatch, make_video("approved"), connected=False)
    assert any("connect_youtube" in w.value for w in app.warning)


def test_panel_shows_publish_and_schedule_buttons_when_connected(monkeypatch):
    app = run_app(monkeypatch, make_video("approved"), connected=True)
    labels = [b.label for b in app.button]
    assert "Abhi publish karein" in labels
    assert "Schedule karein" in labels


def test_panel_shows_published_state(monkeypatch):
    app = run_app(monkeypatch, make_video("published", youtube_id="abc", privacy="private"))
    assert any("upload ho gayi" in s.value for s in app.success)
