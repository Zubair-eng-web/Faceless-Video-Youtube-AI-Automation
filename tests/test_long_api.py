import threading
from types import SimpleNamespace as NS

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.seo_agent import SEOPack
from app.api.long_routes import register_long_routes
from app.core import db
from app.services.long_pipeline import write_progress
from app.services.long_quality import QAReport

CALLS = []


def fake_runner(**kw):
    CALLS.append(kw)
    write_progress(kw["run_dir"], status="done", stage="done", pct=100)
    return NS(topic=kw["topic"], language=kw["language"], status="ready", run_dir=str(kw["run_dir"]),
              video_path="v.mp4", thumbnail_path="t.jpg", title="T", duration=60.0,
              seo=SEOPack(title="T", description="d", hashtags=["#a"], tags=["x"], thumbnail_text="hi"),
              quality=QAReport())


def make(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    CALLS.clear()
    app = FastAPI()
    register_long_routes(app, p, runner=fake_runner, lock=threading.Lock(), output_dir=tmp_path / "out")
    return TestClient(app), p


def test_generate_list_resume_approve(tmp_path):
    c, p = make(tmp_path)
    r = c.post("/long/generate", json={"topic": "Black holes", "minutes": 5})
    assert r.status_code == 202
    vid = r.json()["id"]
    row = c.get("/long").json()[0]
    assert row["id"] == vid and row["status"] == "ready" and row["pct"] == 100
    d = c.get(f"/videos/{vid}/long").json()
    assert d["params"]["minutes"] == 5 and d["progress"]["status"] == "done"
    assert c.post(f"/videos/{vid}/long/resume").status_code == 202 and len(CALLS) == 2
    assert c.post(f"/videos/{vid}/long/approve").json()["status"] == "approved"
    assert c.post(f"/videos/{vid}/long/approve").status_code == 409


def test_series_style_reaches_runner(tmp_path):
    c, p = make(tmp_path)
    s = c.post("/series", json={"name": "Cosmos", "tone": "warm"}).json()
    vid = c.post("/long/generate", json={"topic": "Stars", "series_id": s["id"]}).json()["id"]
    assert CALLS[-1]["style"].name == "Cosmos" and CALLS[-1]["style"].episode == 1
    assert db.get_video(p, vid)["episode_no"] == 1
    assert c.post("/long/generate", json={"topic": "Stars", "series_id": 999}).status_code == 404
