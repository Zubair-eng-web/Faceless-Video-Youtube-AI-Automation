import json
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

from dashboard import ops_helpers as O
from dashboard.api_client import ApiClient, ApiError

APP_FILE = Path(__file__).resolve().parents[1] / "dashboard" / "streamlit_app.py"


def test_format_count():
    assert O.format_count(None) == "-"
    assert O.format_count(950) == "950"
    assert O.format_count(1500) == "1.5K"
    assert O.format_count(2_500_000) == "2.5M"


def test_engagement_text():
    assert O.engagement_text(0.075) == "7.5%"
    assert O.engagement_text(None) == "0.0%"


def test_schedule_summary():
    assert O.schedule_summary({"daily_videos": 0, "produce_at": "09:00", "video_seconds": 40}) == "Band"
    assert O.schedule_summary({"daily_videos": 2, "produce_at": "09:00", "video_seconds": 40}) == "Roz 2 videos, 09:00 ke baad, 40s"


def test_analytics_rows():
    rows = O.analytics_rows([
        {"id": 1, "title": "A", "views": 200, "likes": 10, "comments": 2, "stats_at": "2026-11-06T10:00:00"},
        {"id": 2, "title": None, "topic": "T", "views": None, "likes": None, "comments": None, "stats_at": None},
    ])
    assert rows[0]["Views"] == "200"
    assert rows[0]["Engagement"] == "6.0%"
    assert rows[0]["Updated"] == "2026-11-06 10:00:00"
    assert rows[1]["Title"] == "T"
    assert (rows[1]["Views"], rows[1]["Engagement"], rows[1]["Updated"]) == ("-", "-", "-")


def test_refresh_message():
    assert "2 videos" in O.refresh_message({"updated": 2, "needs_reconnect": [], "errors": []})
    message = O.refresh_message({"updated": 0, "needs_reconnect": [3], "errors": ["boom"]})
    assert "connect_youtube 3" in message
    assert "boom" in message


def test_client_production_and_analytics_calls():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.content))
        return httpx.Response(200, json={})

    client = ApiClient("http://api.test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    client.production()
    client.set_schedule(2, 3, "09:30", 30)
    client.refresh_analytics()
    client.analytics()
    client.insights()
    assert [(m, p) for m, p, _ in seen] == [
        ("GET", "/production"),
        ("PUT", "/channels/2/schedule"),
        ("POST", "/analytics/refresh"),
        ("GET", "/analytics"),
        ("POST", "/analytics/insights"),
    ]
    assert json.loads(seen[1][2]) == {"daily_videos": 3, "produce_at": "09:30", "video_seconds": 30}


# ---------- Streamlit smoke tests ----------
class Resp:
    def __init__(self, data=None):
        self._data = data

    def json(self):
        return self._data


def run_page(monkeypatch, page, extra):
    def fake(self, method, path, **kwargs):
        if path in extra:
            return Resp(extra[path])
        if path == "/health":
            return Resp({"status": "ok"})
        if path == "/stats":
            return Resp({"total": 0})
        if path in ("/channels", "/videos"):
            return Resp([])
        raise ApiError("fake: " + path)

    monkeypatch.setattr(ApiClient, "_request", fake)
    app = AppTest.from_file(str(APP_FILE), default_timeout=20)
    app.run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception
    return app


def test_production_page_renders(monkeypatch):
    info = {"auto_produce": False, "check_minutes": 10, "channels": [{
        "id": 1, "name": "Space", "niche": "space", "language": "English", "daily_videos": 2,
        "produce_at": "09:00", "video_seconds": 40, "produced_today": 1, "failed_today": 0}]}
    app = run_page(monkeypatch, "Production", {"/production": info})
    assert app.subheader[0].value.startswith("Production")
    assert any("OFF" in w.value for w in app.warning)
    assert any("Space" in m.value for m in app.markdown)


def test_analytics_page_renders(monkeypatch):
    data = {
        "summary": {"videos": 1, "total_views": 1500, "avg_views": 1500.0, "engagement": 0.05,
                    "best": {"id": 1, "title": "Moon", "views": 1500}},
        "videos": [{"id": 1, "channel_id": 1, "title": "Moon", "topic": "Moon", "youtube_id": "yt1",
                    "privacy": "private", "published_at": "2026-11-06T10:00:00", "views": 1500,
                    "likes": 50, "comments": 25, "stats_at": "2026-11-06T11:00:00"}],
    }
    app = run_page(monkeypatch, "Analytics", {"/analytics": data})
    assert app.subheader[0].value == "Analytics"
    labels = [m.label for m in app.metric]
    assert len(app.metric) == 4
    assert "Videos (stats ke saath)" in labels
    assert "Total videos" in labels
