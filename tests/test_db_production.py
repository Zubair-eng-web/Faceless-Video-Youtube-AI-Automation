from datetime import datetime

import pytest

from app.core import db, db_production


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "app.db"
    db.init_db(p)
    return p


def make_channel(path, name="C", niche="space"):
    return db.create_channel(path, name, niche=niche)["id"]


def test_migration_adds_production_and_stats_columns(path):
    with db.connect(path) as con:
        video_cols = {r["name"] for r in con.execute("PRAGMA table_info(videos)")}
        channel_cols = {r["name"] for r in con.execute("PRAGMA table_info(channels)")}
    assert {"views", "likes", "comments", "stats_at"} <= video_cols
    assert {"daily_videos", "produce_at", "video_seconds"} <= channel_cols
    channel = db.get_channel(path, make_channel(path))
    assert (channel["daily_videos"], channel["produce_at"], channel["video_seconds"]) == (0, "09:00", 40)


def test_set_schedule_saves_and_normalizes_time(path):
    cid = make_channel(path)
    row = db_production.set_channel_schedule(path, cid, 2, "9:05", 30)
    assert (row["daily_videos"], row["produce_at"], row["video_seconds"]) == (2, "09:05", 30)


def test_set_schedule_validates_input(path):
    cid = make_channel(path)
    for args in ((6, "09:00", 40), (-1, "09:00", 40), (1, "25:00", 40), (1, "kal", 40), (1, "09:00", 5)):
        with pytest.raises(ValueError):
            db_production.set_channel_schedule(path, cid, *args)


def test_schedule_needs_niche_unless_turned_off(path):
    cid = make_channel(path, niche="")
    with pytest.raises(ValueError, match="niche"):
        db_production.set_channel_schedule(path, cid, 1, "09:00", 40)
    assert db_production.set_channel_schedule(path, cid, 0, "09:00", 40)["daily_videos"] == 0


def test_set_schedule_unknown_channel(path):
    with pytest.raises(db.NotFoundError):
        db_production.set_channel_schedule(path, 999, 1, "09:00", 40)


def test_scheduled_channels_only_returns_active_ones(path):
    make_channel(path, "A")
    b = make_channel(path, "B")
    db_production.set_channel_schedule(path, b, 1, "10:00", 40)
    assert [c["id"] for c in db_production.scheduled_channels(path)] == [b]


def test_count_today_splits_failed_and_ignores_other_days(path):
    cid = make_channel(path)
    db.create_job(path, cid, "a", "English")
    bad = db.create_job(path, cid, "b", "English")
    db.fail_video(path, bad, "x")
    old = db.create_job(path, cid, "c", "English")
    with db.connect(path) as con:
        con.execute("UPDATE videos SET created_at = '2000-01-01T00:00:00' WHERE id = ?", (old,))
    today = datetime.now().date().isoformat()
    assert db_production.count_today(path, cid, today) == (1, 1)


def test_update_video_stats_and_published_queries(path):
    cid = make_channel(path)
    video = db.create_job(path, cid, "a", "English")
    db.create_job(path, cid, "b", "English")  # published nahi, nazar nahi aani chahiye
    with db.connect(path) as con:
        con.execute("UPDATE videos SET status = 'published', youtube_id = 'yt1' WHERE id = ?", (video,))
    assert [v["id"] for v in db_production.published_with_youtube_id(path)] == [video]
    db_production.update_video_stats(path, video, 120, 10, 3)
    row = db.get_video(path, video)
    assert (row["views"], row["likes"], row["comments"]) == (120, 10, 3)
    assert row["stats_at"] is not None
    assert [v["id"] for v in db_production.published_videos(path)] == [video]
