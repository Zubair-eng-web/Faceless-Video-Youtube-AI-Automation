from datetime import datetime

import pytest

from app.agents.seo_agent import SEOPack
from app.core import db, db_publish
from app.pipeline import PipelineResult
from app.services.quality import QualityReport


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "app.db"
    db.init_db(p)
    return p


def make_result(topic="A"):
    return PipelineResult(
        topic=topic, language="English", status="ready", run_dir="run", video_path="v.mp4",
        thumbnail_path="t.jpg", title="Title", duration=20.0,
        seo=SEOPack(title="Title", description="D", hashtags=["#Shorts"], tags=["t"], thumbnail_text="BOOM"),
        quality=QualityReport(issues=[], stats={}),
    )


def approved(path, topic="A"):
    video_id = db.create_job(path, None, topic, "English")
    db.transition(path, video_id, "generating", {"queued"})
    db.finish_video(path, video_id, make_result(topic))
    db.transition(path, video_id, "approved", {"ready"})
    return video_id


def test_migration_adds_publish_columns(path):
    with db.connect(path) as con:
        columns = {r["name"] for r in con.execute("PRAGMA table_info(videos)")}
    assert {"youtube_id", "privacy", "scheduled_at", "published_at", "publish_error"} <= columns


def test_parse_when_formats():
    assert db_publish.parse_when("2026-11-07T10:00") == "2026-11-07T10:00:00"
    assert db_publish.parse_when("2026-11-07 10:30") == "2026-11-07T10:30:00"
    with pytest.raises(ValueError):
        db_publish.parse_when("kal subah")


def test_schedule_only_approved_videos(path):
    queued = db.create_job(path, None, "Q", "English")
    with pytest.raises(db.InvalidTransitionError):
        db_publish.schedule_video(path, queued, "2026-11-07T10:00")
    video_id = approved(path)
    row = db_publish.schedule_video(path, video_id, "2026-11-07T10:00")
    assert row["scheduled_at"] == "2026-11-07T10:00:00"
    with pytest.raises(db.NotFoundError):
        db_publish.schedule_video(path, 999, "2026-11-07T10:00")


def test_unschedule_clears_time(path):
    video_id = approved(path)
    db_publish.schedule_video(path, video_id, "2026-11-07T10:00")
    assert db_publish.unschedule_video(path, video_id)["scheduled_at"] is None


def test_claim_is_atomic(path):
    video_id = approved(path)
    assert db_publish.claim_for_publish(path, video_id)["status"] == "publishing"
    with pytest.raises(db.InvalidTransitionError):
        db_publish.claim_for_publish(path, video_id)


def test_finish_publish_saves_result(path):
    video_id = approved(path)
    db_publish.claim_for_publish(path, video_id)
    db_publish.finish_publish(path, video_id, "yt1", "private", "note")
    video = db.get_video(path, video_id)
    assert video["status"] == "published"
    assert video["youtube_id"] == "yt1"
    assert video["privacy"] == "private"
    assert video["published_at"] is not None
    assert video["publish_error"] == "note"


def test_fail_and_retry_publish(path):
    video_id = approved(path)
    db_publish.schedule_video(path, video_id, "2026-11-07T10:00")
    db_publish.claim_for_publish(path, video_id)
    db_publish.fail_publish(path, video_id, "boom")
    failed = db.get_video(path, video_id)
    assert failed["status"] == "publish_failed"
    assert failed["publish_error"] == "boom"
    row = db_publish.retry_publish(path, video_id)
    assert row["status"] == "approved"
    assert row["publish_error"] is None
    assert row["scheduled_at"] is None
    with pytest.raises(db.InvalidTransitionError):
        db_publish.retry_publish(path, video_id)


def test_release_publish_returns_to_approved_with_note(path):
    video_id = approved(path)
    db_publish.schedule_video(path, video_id, "2026-11-07T10:00")
    db_publish.claim_for_publish(path, video_id)
    db_publish.release_publish(path, video_id, "limit khatam")
    video = db.get_video(path, video_id)
    assert video["status"] == "approved"
    assert video["publish_error"] == "limit khatam"
    assert video["scheduled_at"] == "2026-11-07T10:00:00"


def test_due_videos_only_approved_and_due_in_order(path):
    a, b, c, d = (approved(path, name) for name in "abcd")
    db_publish.schedule_video(path, a, "2026-11-07T12:00")
    db_publish.schedule_video(path, b, "2026-11-07T09:00")
    db_publish.schedule_video(path, c, "2026-11-09T09:00")
    due = db_publish.due_videos(path, "2026-11-08T00:00:00", limit=10)
    assert [v["id"] for v in due] == [b, a]
    db.transition(path, b, "rejected", {"approved"})
    assert [v["id"] for v in db_publish.due_videos(path, "2026-11-08T00:00:00", limit=10)] == [a]


def test_published_today_counts_by_day(path):
    for name in "ab":
        video_id = approved(path, name)
        db_publish.finish_publish(path, video_id, "yt", "private")
    today = datetime.now().date().isoformat()
    assert db_publish.published_today(path, today) == 2
    assert db_publish.published_today(path, "2000-01-01") == 0


def test_mark_stale_publishes(path):
    a = approved(path, "a")
    b = approved(path, "b")
    db_publish.claim_for_publish(path, a)
    assert db_publish.mark_stale_publishes(path) == 1
    stale = db.get_video(path, a)
    assert stale["status"] == "publish_failed"
    assert "Studio" in stale["publish_error"]
    assert db.get_video(path, b)["status"] == "approved"
