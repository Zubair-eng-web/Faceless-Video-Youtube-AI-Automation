from datetime import datetime

import pytest

from app.agents.seo_agent import SEOPack
from app.core import db, db_production
from app.pipeline import PipelineResult
from app.services.production import MAX_FAILED_PER_DAY, produce_due
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
        self.calls.append(dict(topic=topic, niche=niche, language=language, seconds=seconds,
                               voice=voice, used_topics=list(used_topics)))
        if self.error:
            raise RuntimeError(self.error)
        return PipelineResult(
            topic=f"Topic {len(self.calls)}", language=language, status="ready", run_dir="r",
            video_path="v.mp4", thumbnail_path="t.jpg", title="T", duration=20.0,
            seo=SEOPack(title="T", description="D", hashtags=["#Shorts"], tags=["t"], thumbnail_text="BOOM"),
            quality=QualityReport(issues=[], stats={}),
        )


def make_channel(path, name="C", niche="space", daily=2, at="00:00", language="English", voice=None, seconds=40):
    cid = db.create_channel(path, name, niche=niche, language=language, voice=voice)["id"]
    db_production.set_channel_schedule(path, cid, daily, at, seconds)
    return cid


def test_produces_one_video_per_channel_per_tick(path):
    a = make_channel(path, "A")
    b = make_channel(path, "B")
    made = produce_due(path, Runner())
    assert len(made) == 2
    assert {db.get_video(path, v)["channel_id"] for v in made} == {a, b}
    assert all(db.get_video(path, v)["status"] == "ready" for v in made)


def test_skips_channel_before_its_start_time(path):
    make_channel(path, at="09:00")
    runner = Runner()
    assert produce_due(path, runner, now=lambda: datetime(2026, 11, 6, 8, 0)) == []
    assert runner.calls == []


def test_stops_at_daily_limit(path):
    make_channel(path, daily=2)
    runner = Runner()
    assert len(produce_due(path, runner)) == 1
    assert len(produce_due(path, runner)) == 1
    assert produce_due(path, runner) == []
    assert len(runner.calls) == 2


def test_manual_videos_count_toward_daily_limit(path):
    cid = make_channel(path, daily=1)
    db.create_job(path, cid, "manual", "English")
    assert produce_due(path, Runner()) == []


def test_stops_after_repeated_failures(path):
    make_channel(path, daily=5)
    runner = Runner(error="gemini down")
    for _ in range(MAX_FAILED_PER_DAY + 3):
        produce_due(path, runner)
    assert len(runner.calls) == MAX_FAILED_PER_DAY


def test_failure_is_recorded_on_the_video(path):
    make_channel(path, daily=1)
    made = produce_due(path, Runner(error="gemini down"))
    video = db.get_video(path, made[0])
    assert video["status"] == "failed"
    assert "gemini down" in video["error"]


def test_runner_gets_channel_settings_and_used_topics(path):
    make_channel(path, niche="space facts", daily=2, language="Spanish", voice="es-ES-AlvaroNeural", seconds=30)
    runner = Runner()
    produce_due(path, runner)
    produce_due(path, runner)
    first, second = runner.calls
    assert first["topic"] is None
    assert (first["niche"], first["language"], first["voice"], first["seconds"]) == (
        "space facts", "Spanish", "es-ES-AlvaroNeural", 30)
    assert first["used_topics"] == []
    assert second["used_topics"] == ["Topic 1"]


def test_ignores_channels_without_schedule_or_niche(path):
    make_channel(path, "Off", daily=0)
    no_niche = make_channel(path, "NoNiche", daily=1)
    with db.connect(path) as con:
        con.execute("UPDATE channels SET niche = '' WHERE id = ?", (no_niche,))
    runner = Runner()
    assert produce_due(path, runner) == []
    assert runner.calls == []
