"""Publishing ke database functions: schedule, claim, nateeja."""
from datetime import datetime

from app.core.db import InvalidTransitionError, NotFoundError, _now, connect

STALE_PUBLISH_MESSAGE = (
    "Server band hone se upload adhoori reh gayi. YouTube Studio me check karein ke video "
    "upload to nahi ho gayi, phir retry karein."
)


def parse_when(value: str) -> str:
    """'2026-11-07T10:00' ya '2026-11-07 10:00' ko local time ki ISO string banata hai."""
    try:
        moment = datetime.fromisoformat(value.strip().replace(" ", "T"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Waqt ka format ghalat hai, aise likhein: 2026-11-07T10:00") from exc
    if moment.tzinfo is not None:
        moment = moment.astimezone().replace(tzinfo=None)
    return moment.replace(microsecond=0).isoformat()


def _get(con, video_id: int):
    row = con.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Video {video_id} nahi mili")
    return row


def schedule_video(db_path, video_id: int, when: str) -> dict:
    when = parse_when(when)
    with connect(db_path) as con:
        row = _get(con, video_id)
        if row["status"] != "approved":
            raise InvalidTransitionError(row["status"], "scheduled")
        con.execute("UPDATE videos SET scheduled_at = ?, updated_at = ? WHERE id = ?", (when, _now(), video_id))
        return dict(_get(con, video_id))


def unschedule_video(db_path, video_id: int) -> dict:
    with connect(db_path) as con:
        _get(con, video_id)
        con.execute("UPDATE videos SET scheduled_at = NULL, updated_at = ? WHERE id = ?", (_now(), video_id))
        return dict(_get(con, video_id))


def claim_for_publish(db_path, video_id: int) -> dict:
    """approved se publishing: ek hi baar kaamyab hota hai (dobara click par error)."""
    with connect(db_path) as con:
        cur = con.execute(
            "UPDATE videos SET status = 'publishing', publish_error = NULL, updated_at = ? "
            "WHERE id = ? AND status = 'approved'",
            (_now(), video_id),
        )
        row = _get(con, video_id)
        if cur.rowcount == 0:
            raise InvalidTransitionError(row["status"], "publishing")
        return dict(row)


def finish_publish(db_path, video_id: int, youtube_id: str, privacy: str, note=None) -> None:
    now = _now()
    with connect(db_path) as con:
        con.execute(
            "UPDATE videos SET status = 'published', youtube_id = ?, privacy = ?, published_at = ?, "
            "publish_error = ?, updated_at = ? WHERE id = ?",
            (youtube_id, privacy, now, note, now, video_id),
        )


def fail_publish(db_path, video_id: int, error: str) -> None:
    with connect(db_path) as con:
        con.execute(
            "UPDATE videos SET status = 'publish_failed', publish_error = ?, updated_at = ? WHERE id = ?",
            (error[:2000], _now(), video_id),
        )


def release_publish(db_path, video_id: int, note: str) -> None:
    """Upload shuru na ho saka (jaise quota khatam): video wapas approved, schedule barqarar."""
    with connect(db_path) as con:
        con.execute(
            "UPDATE videos SET status = 'approved', publish_error = ?, updated_at = ? WHERE id = ?",
            (note[:2000], _now(), video_id),
        )


def retry_publish(db_path, video_id: int) -> dict:
    with connect(db_path) as con:
        cur = con.execute(
            "UPDATE videos SET status = 'approved', publish_error = NULL, scheduled_at = NULL, updated_at = ? "
            "WHERE id = ? AND status = 'publish_failed'",
            (_now(), video_id),
        )
        row = _get(con, video_id)
        if cur.rowcount == 0:
            raise InvalidTransitionError(row["status"], "approved")
        return dict(row)


def due_videos(db_path, now_iso: str, limit: int = 10) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM videos WHERE status = 'approved' AND scheduled_at IS NOT NULL "
            "AND scheduled_at <= ? ORDER BY scheduled_at, id LIMIT ?",
            (now_iso, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def published_today(db_path, day: str) -> int:
    """day = 'YYYY-MM-DD'."""
    with connect(db_path) as con:
        return con.execute(
            "SELECT COUNT(*) FROM videos WHERE status = 'published' AND published_at LIKE ?",
            (day + "%",),
        ).fetchone()[0]


def mark_stale_publishes(db_path) -> int:
    with connect(db_path) as con:
        return con.execute(
            "UPDATE videos SET status = 'publish_failed', publish_error = ?, updated_at = ? "
            "WHERE status = 'publishing'",
            (STALE_PUBLISH_MESSAGE, _now()),
        ).rowcount
