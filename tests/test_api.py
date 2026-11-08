import pytest
from fastapi.testclient import TestClient

from app.agents.seo_agent import SEOPack
from app.api.main import create_app
from app.api.runner import pick_topic
from app.core import db
from app.core.models import TopicIdea
from app.pipeline import PipelineError, PipelineResult
from app.services.quality import QualityReport


class FakeRunner:
    def __init__(self, tmp_path, status="ready", error=None):
        self.tmp_path = tmp_path
        self.status = status
        self.error = error
        self.calls = []

    def __call__(self, topic, niche, language, seconds, voice, used_topics):
        self.calls.append(dict(topic=topic, niche=niche, language=language, seconds=seconds,
                               voice=voice, used_topics=list(used_topics)))
        if self.error:
            raise PipelineError("voiceover", self.error)
        video = self.tmp_path / "video.mp4"
        video.write_bytes(b"video-bytes")
        thumb = self.tmp_path / "thumb.jpg"
        thumb.write_bytes(b"jpg")
        return PipelineResult(
            topic=topic or f"Auto topic {len(self.calls)}", language=language, status=self.status,
            run_dir=str(self.tmp_path), video_path=str(video), thumbnail_path=str(thumb),
            title="Title", duration=40.0,
            seo=SEOPack(title="Title", description="D", hashtags=["#Shorts"], tags=["t"], thumbnail_text="BOOM"),
            quality=QualityReport(issues=[], stats={}),
        )


def make_client(tmp_path, **kwargs):
    runner = FakeRunner(tmp_path, **kwargs)
    return TestClient(create_app(db_path=tmp_path / "t.db", runner=runner)), runner


def make_channel(client, name="C", **extra):
    response = client.post("/channels", json={"name": name, **extra})
    assert response.status_code == 201
    return response.json()


def generate(client, **body):
    response = client.post("/generate", json=body)
    assert response.status_code == 202
    return response.json()["id"]


def test_health(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/health").json() == {"status": "ok"}


def test_channel_crud(tmp_path):
    client, _ = make_client(tmp_path)
    channel = make_channel(client, "Space Facts", niche="space", language="English")
    assert [c["name"] for c in client.get("/channels").json()] == ["Space Facts"]
    assert client.get(f"/channels/{channel['id']}").json()["niche"] == "space"
    assert client.delete(f"/channels/{channel['id']}").json() == {"deleted": True}
    assert client.get(f"/channels/{channel['id']}").status_code == 404


def test_duplicate_channel_is_409(tmp_path):
    client, _ = make_client(tmp_path)
    make_channel(client, "Space")
    assert client.post("/channels", json={"name": "space"}).status_code == 409


def test_channel_with_unknown_language_is_422(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.post("/channels", json={"name": "X", "language": "Klingon"}).status_code == 422


def test_generate_with_topic_runs_job_in_background(tmp_path):
    client, runner = make_client(tmp_path)
    video_id = generate(client, topic="Black holes")
    video = client.get(f"/videos/{video_id}").json()
    assert video["status"] == "ready"
    assert video["topic"] == "Black holes"
    assert video["title"] == "Title"
    assert video["seo"]["title"] == "Title"
    assert runner.calls[0]["seconds"] == 40


def test_generate_needs_topic_or_niche(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.post("/generate", json={}).status_code == 422


def test_generate_uses_channel_defaults(tmp_path):
    client, runner = make_client(tmp_path)
    channel = make_channel(client, niche="space facts", language="Spanish", voice="es-ES-AlvaroNeural")
    generate(client, channel_id=channel["id"])
    call = runner.calls[0]
    assert call["topic"] is None
    assert call["niche"] == "space facts"
    assert call["language"] == "Spanish"
    assert call["voice"] == "es-ES-AlvaroNeural"


def test_request_overrides_channel_defaults(tmp_path):
    client, runner = make_client(tmp_path)
    channel = make_channel(client, niche="space facts", language="Spanish", voice="es-ES-AlvaroNeural")
    generate(client, channel_id=channel["id"], language="French", topic="X")
    call = runner.calls[0]
    assert call["language"] == "French"
    assert call["topic"] == "X"
    assert call["niche"] == "space facts"


def test_used_topics_are_passed_to_runner(tmp_path):
    client, runner = make_client(tmp_path)
    channel = make_channel(client, niche="space facts")
    generate(client, channel_id=channel["id"], topic="A")
    generate(client, channel_id=channel["id"])
    assert runner.calls[1]["used_topics"] == ["A"]


def test_generate_unknown_channel_is_404(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.post("/generate", json={"topic": "A", "channel_id": 99}).status_code == 404


def test_failed_job_is_recorded(tmp_path):
    client, _ = make_client(tmp_path, error="mic nahi chala")
    video_id = generate(client, topic="A")
    video = client.get(f"/videos/{video_id}").json()
    assert video["status"] == "failed"
    assert "voiceover" in video["error"]
    assert "mic nahi chala" in video["error"]


def test_approve_and_reject(tmp_path):
    client, _ = make_client(tmp_path)
    video_id = generate(client, topic="A")
    assert client.post(f"/videos/{video_id}/approve").json()["status"] == "approved"
    assert client.post(f"/videos/{video_id}/reject").json()["status"] == "rejected"


def test_needs_review_video_can_be_approved(tmp_path):
    client, _ = make_client(tmp_path, status="needs_review")
    video_id = generate(client, topic="A")
    assert client.get(f"/videos/{video_id}").json()["status"] == "needs_review"
    assert client.post(f"/videos/{video_id}/approve").json()["status"] == "approved"


def test_approving_a_failed_video_is_409(tmp_path):
    client, _ = make_client(tmp_path, error="x")
    video_id = generate(client, topic="A")
    assert client.post(f"/videos/{video_id}/approve").status_code == 409


def test_list_videos_filters_by_status_and_channel(tmp_path):
    client, _ = make_client(tmp_path)
    a = make_channel(client, "A")
    b = make_channel(client, "B")
    generate(client, channel_id=a["id"], topic="X")
    generate(client, channel_id=b["id"], topic="Y")
    assert len(client.get("/videos").json()) == 2
    assert len(client.get(f"/videos?channel_id={a['id']}").json()) == 1
    assert len(client.get("/videos?status=ready").json()) == 2
    assert client.get("/videos?status=failed").json() == []


def test_video_and_thumbnail_files(tmp_path):
    client, runner = make_client(tmp_path)
    video_id = generate(client, topic="A")
    assert client.get(f"/videos/{video_id}/file").content == b"video-bytes"
    assert client.get(f"/videos/{video_id}/thumbnail").content == b"jpg"
    (tmp_path / "video.mp4").unlink()
    assert client.get(f"/videos/{video_id}/file").status_code == 404


def test_unknown_video_is_404(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/videos/999").status_code == 404
    assert client.post("/videos/999/approve").status_code == 404


def test_stale_jobs_are_failed_on_startup(tmp_path):
    path = tmp_path / "t.db"
    db.init_db(path)
    db.create_job(path, None, "Old", "English")
    client = TestClient(create_app(db_path=path, runner=FakeRunner(tmp_path)))
    assert client.get("/videos/1").json()["status"] == "failed"


def test_stats_endpoint(tmp_path):
    client, _ = make_client(tmp_path)
    generate(client, topic="A")
    assert client.get("/stats").json() == {"ready": 1, "total": 1}


def topic(title):
    return TopicIdea(title=title, angle="a", why_trending="w")


def test_pick_topic_skips_used_topics():
    assert pick_topic([topic("A"), topic("B")], ["  a "]) == "B"


def test_pick_topic_returns_first_when_all_used():
    assert pick_topic([topic("A"), topic("B")], ["A", "B"]) == "A"


def test_pick_topic_rejects_empty_list():
    with pytest.raises(ValueError):
        pick_topic([], [])
