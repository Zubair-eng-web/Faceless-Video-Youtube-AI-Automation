from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

from dashboard.api_client import ApiClient, ApiError

APP_FILE = Path(__file__).resolve().parents[1] / "dashboard" / "streamlit_app.py"


class Resp:
    def __init__(self, data=None):
        self._data = data

    def json(self):
        return self._data


def test_client_create_variations_call():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        return httpx.Response(202, json={"videos": []})

    client = ApiClient("http://api.test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    client.create_variations(2, "Moon", ["English", "Urdu"])
    assert seen == [("POST", "/channels/2/variations")]


def test_variations_page_renders(monkeypatch):
    channels = [{"id": 1, "name": "Space", "niche": "space", "language": "English"}]

    def fake(self, method, path, **kwargs):
        if path == "/health":
            return Resp({"status": "ok"})
        if path == "/stats":
            return Resp({"total": 0})
        if path == "/channels":
            return Resp(channels)
        if path == "/videos":
            return Resp([])
        raise ApiError("fake: " + path)

    monkeypatch.setattr(ApiClient, "_request", fake)
    app = AppTest.from_file(str(APP_FILE), default_timeout=20)
    app.run()
    app.sidebar.radio[0].set_value("Variations").run()
    assert not app.exception
    assert app.subheader[0].value.startswith("Variations")
