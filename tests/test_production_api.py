import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import db, db_production
from app.services.gemini_client import GeminiError


def no_runner(**kwargs):
    raise AssertionError("runner nahi chalna chahiye")


def make(tmp_path, stats_fn=None, insights_fn=None):
    app = create_app(
        db_path=tmp_path / "t.db", runner=no_runner, uploader=lambda *a, **k: None,
        auto_publish=False, auto_produce=False,
        stats_fn=stats_fn or (lambda p: {"updated": 0, "needs_reconnect": [], "errors": []}),
        insights_fn=insights_fn or (lambda videos: {}),
    )
    return TestClient(app)


def channel(client, name="C", niche="space"):
    return client.post("/channels", json={"name": name, "niche": niche}).json()["id"]


def test_set_and_read_channel_schedule(tmp_path):
    client = make(tmp_path)
    cid = channel(client)
    response = client.put(f"/channels/{cid}/schedule", json={"daily_videos": 2, "produce_at": "9:30", "video_seconds": 30})
    assert response.status_code == 200
    assert response.json()["produce_at"] == "09:30"
    listed = client.get("/channels").json()[0]
    assert (listed["daily_videos"], listed["video_seconds"]) == (2, 30)


def test_schedule_validation_errors(tmp_path):
    client = make(tmp_path)
    cid = channel(client)
    assert client.put(f"/channels/{cid}/schedule", json={"daily_videos": 9}).status_code == 422
    assert client.put(f"/channels/{cid}/schedule", json={"daily_videos": 1, "produce_at": "abc"}).status_code == 422
    no_niche = channel(client, "NoNiche", niche="")
    assert client.put(f"/channels/{no_niche}/schedule", json={"daily_videos": 1}).status_code == 422
    assert client.put("/channels/999/schedule", json={"daily_videos": 1}).status_code == 404


def test_production_overview_counts_todays_videos(tmp_path):
    client = make(tmp_path)
    cid = channel(client)
    client.put(f"/channels/{cid}/schedule", json={"daily_videos": 2, "produce_at": "08:00"})
    db.create_job(tmp_path / "t.db", cid, "a", "English")
    info = client.get("/production").json()
    assert info["auto_produce"] is False
    row = info["channels"][0]
    assert (row["daily_videos"], row["produced_today"], row["failed_today"]) == (2, 1, 0)


def test_refresh_calls_stats_function(tmp_path):
    seen = []

    def stats(path):
        seen.append(path)
        return {"updated": 3, "needs_reconnect": [], "errors": []}

    client = make(tmp_path, stats_fn=stats)
    assert client.post("/analytics/refresh").json()["updated"] == 3
    assert len(seen) == 1


def test_analytics_lists_published_videos_with_summary(tmp_path):
    client = make(tmp_path)
    cid = channel(client)
    path = tmp_path / "t.db"
    video = db.create_job(path, cid, "Moon", "English")
    with db.connect(path) as con:
        con.execute("UPDATE videos SET status = 'published', youtube_id = 'yt1' WHERE id = ?", (video,))
    db_production.update_video_stats(path, video, 50, 5, 1)
    data = client.get("/analytics").json()
    assert data["summary"]["videos"] == 1
    assert data["videos"][0]["views"] == 50
    assert data["videos"][0]["youtube_id"] == "yt1"


def test_insights_success_and_not_enough_data(tmp_path):
    client = make(tmp_path, insights_fn=lambda videos: {"summary": "ok"})
    assert client.post("/analytics/insights").json() == {"summary": "ok"}

    def too_few(videos):
        raise ValueError("kam videos")

    client = make(tmp_path / "other", insights_fn=too_few) if (tmp_path / "other").mkdir() is None else None
    assert client.post("/analytics/insights").status_code == 422


def test_insights_gemini_error_is_502(tmp_path):
    def broken(videos):
        raise GeminiError("limit")

    client = make(tmp_path, insights_fn=broken)
    assert client.post("/analytics/insights").status_code == 502
