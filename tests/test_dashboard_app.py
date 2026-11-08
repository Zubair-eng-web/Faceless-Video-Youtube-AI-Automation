import io
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from dashboard.api_client import ApiClient, ApiError

APP_FILE = Path(__file__).resolve().parents[1] / "dashboard" / "streamlit_app.py"

CHANNEL = {"id": 1, "name": "Space", "niche": "space facts", "language": "English", "voice": None,
           "created_at": "2026-11-06T09:00:00"}
VIDEO = {
    "id": 1, "channel_id": 1, "topic": "Moon", "language": "English", "status": "ready",
    "title": "Moon Silence", "duration": 20.5, "error": None, "run_dir": "r",
    "created_at": "2026-11-06T09:00:00", "updated_at": "2026-11-06T09:00:03",
    "seo": {"title": "Moon Silence", "description": "Desc", "hashtags": ["#Shorts"], "tags": ["moon"],
            "thumbnail_text": "THE MOON"},
    "quality": {"issues": [], "stats": {}},
}


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), (10, 20, 30)).save(buffer, "PNG")
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, data=None, content=b""):
        self._data = data
        self.content = content

    def json(self):
        return self._data


def fake_request(self, method, path, **kwargs):
    if path == "/health":
        return FakeResponse({"status": "ok"})
    if path == "/stats":
        return FakeResponse({"ready": 1, "total": 1})
    if path == "/channels":
        return FakeResponse([CHANNEL])
    if path == "/videos":
        return FakeResponse([VIDEO])
    if path == "/videos/1":
        return FakeResponse(VIDEO)
    if path == "/videos/1/thumbnail":
        return FakeResponse(content=png_bytes())
    raise ApiError("fake: " + path)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(ApiClient, "_request", fake_request)
    return AppTest.from_file(str(APP_FILE), default_timeout=20)


def test_videos_page_shows_the_video(app):
    app.run()
    assert not app.exception
    assert app.subheader[0].value == "Videos"
    assert any("Moon Silence" in m.value for m in app.markdown)


def test_generate_page_renders(app):
    app.run()
    app.sidebar.radio[0].set_value("Generate").run()
    assert not app.exception
    assert app.subheader[0].value.startswith("Generate")


def test_channels_page_renders(app):
    app.run()
    app.sidebar.radio[0].set_value("Channels").run()
    assert not app.exception
    assert app.subheader[0].value == "Channels"
    assert any("Space" in m.value for m in app.markdown)


def test_server_down_shows_friendly_error(monkeypatch):
    def down(self, method, path, **kwargs):
        raise ApiError("Server band hai")

    monkeypatch.setattr(ApiClient, "_request", down)
    app = AppTest.from_file(str(APP_FILE), default_timeout=20)
    app.run()
    assert not app.exception
    assert any("Server band hai" in e.value for e in app.error)
