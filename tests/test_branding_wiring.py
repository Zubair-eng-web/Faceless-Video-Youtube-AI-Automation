from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import db
from app.services import captions
from app.services.branding import Branding, add_intro_outro, branding_from_row, build_concat_graph
from app.services.video_editor import build_filter_complex


def _words():
    return [captions.WordTiming(text="hello", start=0.0, end=0.5), captions.WordTiming(text="world", start=0.5, end=1.0)]


def test_captions_default_look_unchanged():
    ass = captions.build_ass(_words())
    assert "{\\c&H00FFFF&}" in ass and "&H00FFFFFF,&H00FFFFFF" in ass


def test_captions_custom_colors():
    ass = captions.build_ass(_words(), highlight_color="#00FF00", text_color="#FF0000")
    assert "{\\c&H00FF00&}" in ass and "{\\c&H0000FF&}" in ass and "&H000000FF,&H000000FF" in ass


def test_filter_complex_without_logo_unchanged():
    fc = build_filter_complex([3, 3])
    assert "[vcap]" not in fc and "[vout]" in fc


def test_filter_complex_with_logo():
    fc = build_filter_complex([3, 3], logo_index=3, logo_opts={"position": "top-left"}, video_width=1080)
    assert "[vcap]" in fc and "[3:v]scale=194:-1" in fc and "overlay=40:40[vout]" in fc


def test_concat_graph_silent_clip_gets_silence():
    g = build_concat_graph([(2.0, False), (10.0, True)], 1080, 1920, 30)
    assert "anullsrc" in g and "[1:a]aresample" in g and "concat=n=2:v=1:a=1[vout][aout]" in g


def test_intro_outro_failure_keeps_video(tmp_path):
    from types import SimpleNamespace
    video = tmp_path / "video.mp4"
    video.write_bytes(b"orig")
    intro = tmp_path / "intro.mp4"
    intro.write_bytes(b"i")
    out = add_intro_outro(video, intro, None, tmp_path, 1080, 1920, 30,
                          runner=lambda cmd, **kw: SimpleNamespace(returncode=1), probe=lambda p: (2.0, True))
    assert out == video and video.read_bytes() == b"orig"


def test_intro_outro_success_replaces_and_keeps_core(tmp_path):
    from pathlib import Path
    from types import SimpleNamespace
    video = tmp_path / "video.mp4"
    video.write_bytes(b"orig")
    intro = tmp_path / "intro.mp4"
    intro.write_bytes(b"i")

    def fake(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"new")
        return SimpleNamespace(returncode=0)

    out = add_intro_outro(video, intro, None, tmp_path, 1080, 1920, 30, runner=fake, probe=lambda p: (2.0, True))
    assert out.read_bytes() == b"new" and (tmp_path / "video_core.mp4").read_bytes() == b"orig"


def test_branding_from_row():
    assert branding_from_row(None) is None
    assert branding_from_row({"branding_json": None}) is None
    assert branding_from_row({"branding_json": "{kharab"}) is None
    assert branding_from_row({"branding_json": '{"font_scale": 1.2}'}).font_scale == 1.2


def test_db_branding_roundtrip(tmp_path):
    path = tmp_path / "t.db"
    db.init_db(path)
    ch = db.create_channel(path, "A")
    assert db.set_channel_branding(path, ch["id"], Branding(font_scale=1.3).model_dump_json())
    assert branding_from_row(db.get_channel(path, ch["id"])).font_scale == 1.3
    assert db.set_channel_branding(path, ch["id"], None)
    assert branding_from_row(db.get_channel(path, ch["id"])) is None
    assert db.set_channel_branding(path, 999, None) is False


def test_api_branding_and_generate_passes_it(tmp_path):
    seen = {}

    def fake(**kw):
        seen.clear()
        seen.update(kw)
        raise RuntimeError("stop")

    c = TestClient(create_app(db_path=tmp_path / "t.db", runner=fake, auto_publish=False, auto_produce=False))
    cid = c.post("/channels", json={"name": "A"}).json()["id"]
    assert c.get(f"/channels/{cid}/branding").json()["highlight_color"] == "#FFFF00"
    r = c.put(f"/channels/{cid}/branding", json={"highlight_color": "#00ff00", "font_scale": 1.2})
    assert r.status_code == 200 and r.json()["highlight_color"] == "#00FF00"
    assert c.put(f"/channels/{cid}/branding", json={"highlight_color": "bad"}).status_code == 422
    assert c.put("/channels/999/branding", json={}).status_code == 404

    assert c.post("/generate", json={"topic": "x", "channel_id": cid}).status_code < 300
    assert seen["branding"].font_scale == 1.2

    cid2 = c.post("/channels", json={"name": "B"}).json()["id"]
    c.post("/generate", json={"topic": "y", "channel_id": cid2})
    assert "branding" not in seen
