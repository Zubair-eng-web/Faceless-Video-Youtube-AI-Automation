import pytest
from fastapi.testclient import TestClient

from app.agents.seo_agent import SEOPack
from app.api.main import create_app
from app.core import db
from app.core.config import settings
from app.pipeline import PipelineResult
from app.services.quality import QualityReport
from app.services.youtube import YouTubeError


class FakeRunner:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.n = 0

    def __call__(self, topic, niche, language, seconds, voice, used_topics):
        self.n += 1
        video = self.tmp_path / f"video{self.n}.mp4"
        video.write_bytes(b"video")
        return PipelineResult(
            topic=topic or "Auto", language=language, status="ready", run_dir=str(self.tmp_path),
            video_path=str(video), thumbnail_path=str(self.tmp_path / "t.jpg"), title="Title", duration=20.0,
            seo=SEOPack(title="Title", description="Desc", hashtags=["#Shorts"], tags=["t"], thumbnail_text="BOOM"),
            quality=QualityReport(issues=[], stats={}),
        )


class FakeUploader:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def __call__(self, channel_id, video_path, title, description, tags=(), thumbnail_path=None,
                 privacy="private", **kwargs):
        self.calls.append(dict(channel_id=channel_id, title=title, privacy=privacy))
        if self.error:
            raise self.error
        return {"video_id": "yt123", "thumbnail_error": None}


def make(tmp_path, error=None):
    uploader = FakeUploader(error)
    app = create_app(db_path=tmp_path / "t.db", runner=FakeRunner(tmp_path), uploader=uploader, auto_publish=False)
    return TestClient(app), uploader


def approved_video(client, with_channel=True):
    body = {"topic": "A"}
    if with_channel:
        body["channel_id"] = client.post("/channels", json={"name": "C"}).json()["id"]
    video_id = client.post("/generate", json=body).json()["id"]
    assert client.post(f"/videos/{video_id}/approve").status_code == 200
    return video_id


def test_publish_requires_approved_video(tmp_path):
    client, _ = make(tmp_path)
    video_id = client.post("/generate", json={"topic": "A"}).json()["id"]
    assert client.post(f"/videos/{video_id}/publish").status_code == 409


def test_publish_uploads_in_background(tmp_path):
    client, uploader = make(tmp_path)
    video_id = approved_video(client)
    response = client.post(f"/videos/{video_id}/publish")
    assert response.status_code == 202
    assert response.json()["status"] == "publishing"
    video = client.get(f"/videos/{video_id}").json()
    assert video["status"] == "published"
    assert video["youtube_id"] == "yt123"
    assert video["privacy"] == settings.default_privacy
    assert uploader.calls[0]["privacy"] == settings.default_privacy


def test_failed_publish_can_be_retried(tmp_path):
    client, uploader = make(tmp_path, error=YouTubeError("boom"))
    video_id = approved_video(client)
    client.post(f"/videos/{video_id}/publish")
    video = client.get(f"/videos/{video_id}").json()
    assert video["status"] == "publish_failed"
    assert "boom" in video["publish_error"]
    uploader.error = None
    assert client.post(f"/videos/{video_id}/retry-publish").json()["status"] == "approved"
    client.post(f"/videos/{video_id}/publish")
    assert client.get(f"/videos/{video_id}").json()["status"] == "published"


def test_publish_without_channel_is_422(tmp_path):
    client, _ = make(tmp_path)
    video_id = approved_video(client, with_channel=False)
    assert client.post(f"/videos/{video_id}/publish").status_code == 422


def test_schedule_and_unschedule(tmp_path):
    client, _ = make(tmp_path)
    video_id = approved_video(client)
    response = client.post(f"/videos/{video_id}/schedule", json={"when": "2026-11-07T10:00"})
    assert response.json()["scheduled_at"] == "2026-11-07T10:00:00"
    assert client.get(f"/videos/{video_id}").json()["scheduled_at"] == "2026-11-07T10:00:00"
    assert client.post(f"/videos/{video_id}/unschedule").json()["scheduled_at"] is None


def test_schedule_rules(tmp_path):
    client, _ = make(tmp_path)
    video_id = approved_video(client)
    assert client.post(f"/videos/{video_id}/schedule", json={"when": "kal subah"}).status_code == 422
    assert client.post("/videos/999/schedule", json={"when": "2026-11-07T10:00"}).status_code == 404
    other = client.post("/generate", json={"topic": "B"}).json()["id"]
    assert client.post(f"/videos/{other}/schedule", json={"when": "2026-11-07T10:00"}).status_code == 409


def test_youtube_channels_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.publish_routes.is_connected", lambda channel_id, tokens_dir=None: channel_id == 1)
    client, _ = make(tmp_path)
    client.post("/channels", json={"name": "One"})
    client.post("/channels", json={"name": "Two"})
    result = {c["name"]: c["connected"] for c in client.get("/youtube/channels").json()}
    assert result == {"One": True, "Two": False}


def test_publishing_info(tmp_path):
    client, _ = make(tmp_path)
    info = client.get("/publishing").json()
    assert info["auto_publish"] is False
    assert info["published_today"] == 0
    assert info["privacy"] == settings.default_privacy
    assert info["daily_limit"] == settings.daily_upload_limit


def test_stale_publishing_video_is_failed_on_startup(tmp_path):
    path = tmp_path / "t.db"
    db.init_db(path)
    video_id = db.create_job(path, None, "A", "English")
    with db.connect(path) as con:
        con.execute("UPDATE videos SET status = 'publishing' WHERE id = ?", (video_id,))
    client = TestClient(create_app(db_path=path, runner=FakeRunner(tmp_path), uploader=FakeUploader(), auto_publish=False))
    assert client.get(f"/videos/{video_id}").json()["status"] == "publish_failed"


def test_video_output_has_publish_fields(tmp_path):
    client, _ = make(tmp_path)
    video_id = client.post("/generate", json={"topic": "A"}).json()["id"]
    video = client.get(f"/videos/{video_id}").json()
    for key in ("youtube_id", "privacy", "scheduled_at", "published_at", "publish_error"):
        assert key in video
        assert video[key] is None


def test_rejecting_a_scheduled_video_stops_publishing(tmp_path):
    client, _ = make(tmp_path)
    video_id = approved_video(client)
    client.post(f"/videos/{video_id}/schedule", json={"when": "2026-11-07T10:00"})
    assert client.post(f"/videos/{video_id}/reject").json()["status"] == "rejected"
    assert client.post(f"/videos/{video_id}/publish").status_code == 409
