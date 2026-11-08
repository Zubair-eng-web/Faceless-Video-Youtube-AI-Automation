"""Production schedule aur stats ke database functions."""
import re

from app.core.db import NotFoundError, _now, connect

MAX_DAILY = 5


def normalize_time(text: str) -> str:
    match = re.match(r"^(\d{1,2}):(\d{2})$", (text or "").strip())
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        raise ValueError("Waqt HH:MM format me likhein, jaise 09:00")
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def set_channel_schedule(db_path, channel_id: int, daily_videos: int, produce_at: str,
                         video_seconds: int = 40) -> dict:
    if not 0 <= daily_videos <= MAX_DAILY:
        raise ValueError(f"Roz ki videos 0 se {MAX_DAILY} ke beech honi chahiye")
    produce_at = normalize_time(produce_at)
    if not 15 <= video_seconds <= 90:
        raise ValueError("Video ki lambai 15 se 90 seconds ke beech honi chahiye")
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Channel {channel_id} nahi mila")
        if daily_videos > 0 and not row["niche"].strip():
            raise ValueError("Auto production ke liye channel ki niche zaroori hai")
        con.execute(
            "UPDATE channels SET daily_videos = ?, produce_at = ?, video_seconds = ? WHERE id = ?",
            (daily_videos, produce_at, video_seconds, channel_id),
        )
        return dict(con.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone())


def scheduled_channels(db_path) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute("SELECT * FROM channels WHERE daily_videos > 0 ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def count_today(db_path, channel_id: int, day: str) -> tuple[int, int]:
    """(bani hui videos, fail hui videos) is din ke liye. day = 'YYYY-MM-DD'."""
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT status, COUNT(*) AS n FROM videos WHERE channel_id = ? AND created_at LIKE ? GROUP BY status",
            (channel_id, day + "%"),
        ).fetchall()
    failed = sum(r["n"] for r in rows if r["status"] == "failed")
    total = sum(r["n"] for r in rows)
    return total - failed, failed


def published_with_youtube_id(db_path) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM videos WHERE status = 'published' AND youtube_id IS NOT NULL ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def published_videos(db_path) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM videos WHERE status = 'published' ORDER BY published_at DESC, id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_video_stats(db_path, video_id: int, views: int, likes: int, comments: int) -> None:
    with connect(db_path) as con:
        con.execute(
            "UPDATE videos SET views = ?, likes = ?, comments = ?, stats_at = ? WHERE id = ?",
            (views, likes, comments, _now(), video_id),
        )
