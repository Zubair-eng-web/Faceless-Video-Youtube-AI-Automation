import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.seo_agent import SEOPack
from app.api.variation_routes import register_variation_routes
from app.core import db
from app.pipeline import PipelineResult
from app.services import variations
from app.services.quality import QualityReport


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "app.db"
    db.init_db(p)
    return p


class Runner:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def __call__(self, topic, niche, language, seconds, voice, used_topics):
        self.calls.append(dict(topic=topic, niche=niche, language=language, seconds=seconds, voice=voice))
        if self.error:
            raise RuntimeError(self.error)
        return PipelineResult(
            topic=topic, language=language, status="ready", run_dir="r", video_path="v.mp4",
            thumbnail_path="t.jpg", title="T", duration=20.0,
            seo=SEOPack(title="T", description="D", hashtags=["#Shorts"], tags=["t"], thumbnail_text="BOOM"),
            quality=QualityReport(issues=[], stats={}),
        )


def make_channel(path, niche="space"):
    return db.create_channel(path, "C", niche=niche)["id"]


def test_clean_languages_dedupes_and_validates():
    assert variations.clean_languages([" English ", "english", "Spanish", ""]) == ["English", "Spanish"]
    with pytest.raises(ValueError):
        variations.clean_languages([])
    with pytest.raises(ValueError):
        variations.clean_languages([f"L{i}" for i in range(variations.MAX_LANGUAGES + 1)])


def test_create_jobs_makes_queued_videos(path):
    cid = make_channel(path)
    _, jobs = variations.create_variation_jobs(path, cid, "Black holes", ["English", "Spanish"])
    assert [lang for _, lang in jobs] == ["English", "Spanish"]
    assert all(db.get_video(path, v)["status"] == "queued" for v, _ in jobs)


def test_create_jobs_rejects_bad_input(path):
    cid = make_channel(path)
    with pytest.raises(ValueError):
        variations.create_variation_jobs(path, cid, "  ", ["English"])
    with pytest.raises(db.NotFoundError):
        variations.create_variation_jobs(path, 999, "Moon", ["English"])


def test_process_variation_success_and_failure(path):
    cid = make_channel(path)
    channel, jobs = variations.create_variation_jobs(path, cid, "Moon", ["Urdu", "French"])
    ok = Runner()
    variations.process_variation(path, ok, channel, jobs[0][0], "Moon", "Urdu")
    assert db.get_video(path, jobs[0][0])["status"] == "ready"
    assert (ok.calls[0]["topic"], ok.calls[0]["language"], ok.calls[0]["voice"]) == ("Moon", "Urdu", None)
    variations.process_variation(path, Runner(error="boom"), channel, jobs[1][0], "Moon", "French")
    video = db.get_video(path, jobs[1][0])
    assert video["status"] == "failed" and "boom" in video["error"]


def test_variations_endpoint(path):
    cid = make_channel(path)
    runner = Runner()
    app = FastAPI()
    register_variation_routes(app, path, runner, spawn=lambda work: work())
    client = TestClient(app)
    response = client.post(f"/channels/{cid}/variations", json={"topic": "Moon", "languages": ["English", "Spanish"]})
    assert response.status_code == 202
    assert [v["language"] for v in response.json()["videos"]] == ["English", "Spanish"]
    assert len(runner.calls) == 2
    assert client.post("/channels/999/variations", json={"topic": "x", "languages": ["English"]}).status_code == 404
    assert client.post(f"/channels/{cid}/variations", json={"topic": "", "languages": ["English"]}).status_code == 422
    assert client.post(f"/channels/{cid}/variations", json={"topic": "x", "languages": []}).status_code == 422
