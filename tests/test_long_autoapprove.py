from tests.test_long_api import make
from app.core import db


def test_auto_approve_only_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("LONG_AUTO_APPROVE", "false")
    c, p = make(tmp_path)
    v1 = c.post("/long/generate", json={"topic": "Stars"}).json()["id"]
    assert db.get_video(p, v1)["status"] == "ready"
    monkeypatch.setenv("LONG_AUTO_APPROVE", "true")
    v2 = c.post("/long/generate", json={"topic": "Planets"}).json()["id"]
    row = db.get_video(p, v2)
    assert row["status"] == "approved" and row["scheduled_at"]
