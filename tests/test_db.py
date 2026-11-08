import json

import pytest

from app.agents.seo_agent import SEOPack
from app.core import db
from app.pipeline import PipelineResult
from app.services.quality import QualityReport


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "data" / "app.db"
    db.init_db(p)
    return p


def make_result(topic="Black Holes", status="ready"):
    return PipelineResult(
        topic=topic, language="English", status=status, run_dir="run", video_path="v.mp4",
        thumbnail_path="t.jpg", title="Title", duration=47.6,
        seo=SEOPack(title="Title", description="D", hashtags=["#Shorts"], tags=["t"], thumbnail_text="BOOM"),
        quality=QualityReport(issues=[], stats={}),
    )


def finished_job(path, channel_id=None, topic="A"):
    video_id = db.create_job(path, channel_id, topic, "English")
    db.transition(path, video_id, "generating", {"queued"})
    db.finish_video(path, video_id, make_result(topic))
    return video_id


def test_init_db_is_idempotent(path):
    db.init_db(path)
    with db.connect(path) as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
        tables = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"channels", "videos"} <= tables


def test_channel_create_list_get(path):
    channel = db.create_channel(path, "  Space   Facts ", niche="space", language="English", voice="v")
    assert channel["name"] == "Space Facts"
    assert db.get_channel(path, channel["id"])["niche"] == "space"
    assert [c["name"] for c in db.list_channels(path)] == ["Space Facts"]
    assert db.get_channel(path, 999) is None


def test_duplicate_channel_name_is_rejected_case_insensitively(path):
    db.create_channel(path, "Space")
    with pytest.raises(db.DuplicateChannelError):
        db.create_channel(path, "space")


def test_empty_channel_name_is_rejected(path):
    with pytest.raises(ValueError):
        db.create_channel(path, "   ")


def test_delete_channel_keeps_its_videos(path):
    channel = db.create_channel(path, "C")
    video_id = db.create_job(path, channel["id"], "A", "English")
    assert db.delete_channel(path, channel["id"]) is True
    assert db.get_video(path, video_id)["channel_id"] is None
    assert db.delete_channel(path, channel["id"]) is False


def test_job_lifecycle_saves_result(path):
    video_id = db.create_job(path, None, "Black Holes", "English")
    assert db.get_video(path, video_id)["status"] == "queued"
    db.transition(path, video_id, "generating", {"queued"})
    db.finish_video(path, video_id, make_result())
    video = db.get_video(path, video_id)
    assert video["status"] == "ready"
    assert video["title"] == "Title"
    assert video["duration"] == 47.6
    assert json.loads(video["seo_json"])["title"] == "Title"


def test_fail_video_records_error(path):
    video_id = db.create_job(path, None, "A", "English")
    db.fail_video(path, video_id, "voiceover toot gaya")
    video = db.get_video(path, video_id)
    assert video["status"] == "failed"
    assert video["error"] == "voiceover toot gaya"


def test_invalid_and_unknown_transitions(path):
    video_id = db.create_job(path, None, "A", "English")
    with pytest.raises(db.InvalidTransitionError) as info:
        db.transition(path, video_id, "approved", {"ready"})
    assert info.value.current == "queued"
    with pytest.raises(db.NotFoundError):
        db.transition(path, 999, "approved", {"ready"})


def test_list_videos_filters_and_orders_newest_first(path):
    c1 = db.create_channel(path, "One")["id"]
    c2 = db.create_channel(path, "Two")["id"]
    v1 = db.create_job(path, c1, "a", "English")
    v2 = db.create_job(path, c1, "b", "English")
    v3 = db.create_job(path, c2, "c", "English")
    db.fail_video(path, v2, "x")
    assert [v["id"] for v in db.list_videos(path)] == [v3, v2, v1]
    assert [v["id"] for v in db.list_videos(path, status="queued")] == [v3, v1]
    assert [v["id"] for v in db.list_videos(path, channel_id=c1)] == [v2, v1]
    assert [v["id"] for v in db.list_videos(path, status="queued", channel_id=c1)] == [v1]


def test_used_topics_skips_failed_and_empty(path):
    channel = db.create_channel(path, "C")["id"]
    finished_job(path, channel, "A")
    bad = db.create_job(path, channel, "B", "English")
    db.fail_video(path, bad, "x")
    db.create_job(path, channel, "", "English")
    assert db.used_topics(path, channel) == ["A"]


def test_mark_stale_jobs(path):
    queued = db.create_job(path, None, "A", "English")
    running = db.create_job(path, None, "B", "English")
    db.transition(path, running, "generating", {"queued"})
    done = finished_job(path, None, "C")
    assert db.mark_stale_jobs(path) == 2
    assert db.get_video(path, queued)["status"] == "failed"
    assert db.get_video(path, running)["status"] == "failed"
    assert db.get_video(path, done)["status"] == "ready"


def test_stats_counts_by_status(path):
    assert db.stats(path) == {"total": 0}
    finished_job(path, None, "A")
    db.create_job(path, None, "B", "English")
    assert db.stats(path) == {"ready": 1, "queued": 1, "total": 2}
