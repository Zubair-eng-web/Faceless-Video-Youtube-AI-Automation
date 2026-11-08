import httpx

from app.core import db
from app.pipeline import core_video
from app.services.branding import Branding
from app.services.production import _branding_kwargs
from dashboard.api_client import ApiClient


def test_api_client_branding_calls():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json={"ok": True})

    c = ApiClient("http://x", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert c.branding(1) == {"ok": True}
    assert c.set_branding(1, {"font_scale": 1.2}) == {"ok": True}
    assert seen == [("GET", "/channels/1/branding"), ("PUT", "/channels/1/branding")]


def test_production_branding_kwargs(tmp_path):
    path = tmp_path / "t.db"
    db.init_db(path)
    ch = db.create_channel(path, "A")
    assert _branding_kwargs(path, ch) == {}
    db.set_channel_branding(path, ch["id"], Branding(font_scale=1.2).model_dump_json())
    assert _branding_kwargs(path, ch)["branding"].font_scale == 1.2


def test_core_video(tmp_path):
    v = tmp_path / "video.mp4"
    v.write_bytes(b"x")
    assert core_video(tmp_path, v) == v
    (tmp_path / "video_core.mp4").write_bytes(b"y")
    assert core_video(tmp_path, v) == tmp_path / "video_core.mp4"
