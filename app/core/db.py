"""SQLite database: channels aur videos."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# Naya column ya table chahiye ho to list me nayi entry jorein, purani na badlein
MIGRATIONS = [
    """
    CREATE TABLE channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        niche TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'English',
        voice TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
        topic TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'English',
        status TEXT NOT NULL,
        title TEXT,
        run_dir TEXT,
        video_path TEXT,
        thumbnail_path TEXT,
        duration REAL,
        seo_json TEXT,
        quality_json TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX idx_videos_status ON videos(status);
    CREATE INDEX idx_videos_channel ON videos(channel_id);
    """,
    """
    ALTER TABLE videos ADD COLUMN youtube_id TEXT;
    ALTER TABLE videos ADD COLUMN privacy TEXT;
    ALTER TABLE videos ADD COLUMN scheduled_at TEXT;
    ALTER TABLE videos ADD COLUMN published_at TEXT;
    ALTER TABLE videos ADD COLUMN publish_error TEXT;
    """,
    """
    ALTER TABLE videos ADD COLUMN views INTEGER;
    ALTER TABLE videos ADD COLUMN likes INTEGER;
    ALTER TABLE videos ADD COLUMN comments INTEGER;
    ALTER TABLE videos ADD COLUMN stats_at TEXT;
    ALTER TABLE channels ADD COLUMN daily_videos INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE channels ADD COLUMN produce_at TEXT NOT NULL DEFAULT '09:00';
    ALTER TABLE channels ADD COLUMN video_seconds INTEGER NOT NULL DEFAULT 40;
    """,
    """
    ALTER TABLE channels ADD COLUMN branding_json TEXT;
    """,
    """
    CREATE TABLE series (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        narrator TEXT NOT NULL DEFAULT '',
        tone TEXT NOT NULL DEFAULT '',
        audience TEXT NOT NULL DEFAULT '',
        visual_json TEXT,
        structure_json TEXT,
        created_at TEXT NOT NULL
    );
    ALTER TABLE videos ADD COLUMN series_id INTEGER;
    ALTER TABLE videos ADD COLUMN episode_no INTEGER;
    """,
]


class NotFoundError(LookupError):
    pass


class DuplicateChannelError(ValueError):
    pass


class InvalidTransitionError(RuntimeError):
    def __init__(self, current: str, target: str):
        super().__init__(f"Status '{current}' se '{target}' nahi ho sakta")
        self.current = current
        self.target = target


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect(db_path):
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(db_path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as con:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        for number, sql in enumerate(MIGRATIONS[version:], start=version + 1):
            con.executescript(sql)
            con.execute(f"PRAGMA user_version = {number}")


# ---------- Channels ----------
def create_channel(db_path, name: str, niche: str = "", language: str = "English", voice=None) -> dict:
    name = " ".join(name.split())
    if not name:
        raise ValueError("Channel ka naam khali hai")
    try:
        with connect(db_path) as con:
            cur = con.execute(
                "INSERT INTO channels (name, niche, language, voice, created_at) VALUES (?, ?, ?, ?, ?)",
                (name, niche.strip(), language, voice, _now()),
            )
            return dict(con.execute("SELECT * FROM channels WHERE id = ?", (cur.lastrowid,)).fetchone())
    except sqlite3.IntegrityError as exc:
        raise DuplicateChannelError(f"'{name}' naam ka channel pehle se maujood hai") from exc


def list_channels(db_path) -> list[dict]:
    with connect(db_path) as con:
        return [dict(r) for r in con.execute("SELECT * FROM channels ORDER BY id").fetchall()]


def get_channel(db_path, channel_id: int) -> dict | None:
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
    return dict(row) if row else None


def delete_channel(db_path, channel_id: int) -> bool:
    with connect(db_path) as con:
        return con.execute("DELETE FROM channels WHERE id = ?", (channel_id,)).rowcount > 0


# ---------- Videos ----------
def create_job(db_path, channel_id, topic: str, language: str) -> int:
    now = _now()
    with connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO videos (channel_id, topic, language, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'queued', ?, ?)",
            (channel_id, topic, language, now, now),
        )
        return cur.lastrowid


def get_video(db_path, video_id: int) -> dict | None:
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    return dict(row) if row else None


def list_videos(db_path, status=None, channel_id=None, limit: int = 50) -> list[dict]:
    where, params = [], []
    if status:
        where.append("status = ?")
        params.append(status)
    if channel_id is not None:
        where.append("channel_id = ?")
        params.append(channel_id)
    sql = "SELECT * FROM videos"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def transition(db_path, video_id: int, new_status: str, allowed_from) -> dict:
    with connect(db_path) as con:
        row = con.execute("SELECT status FROM videos WHERE id = ?", (video_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Video {video_id} nahi mili")
        if row["status"] not in allowed_from:
            raise InvalidTransitionError(row["status"], new_status)
        con.execute("UPDATE videos SET status = ?, updated_at = ? WHERE id = ?", (new_status, _now(), video_id))
        return dict(con.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone())


def finish_video(db_path, video_id: int, result) -> None:
    """Pipeline ka natija (PipelineResult) video ki row me likhna."""
    with connect(db_path) as con:
        cur = con.execute(
            "UPDATE videos SET topic = ?, status = ?, title = ?, run_dir = ?, video_path = ?, "
            "thumbnail_path = ?, duration = ?, seo_json = ?, quality_json = ?, error = NULL, "
            "updated_at = ? WHERE id = ?",
            (result.topic, result.status, result.title, result.run_dir, result.video_path,
             result.thumbnail_path, result.duration, result.seo.model_dump_json(),
             result.quality.model_dump_json(), _now(), video_id),
        )
        if cur.rowcount == 0:
            raise NotFoundError(f"Video {video_id} nahi mili")


def fail_video(db_path, video_id: int, error: str) -> None:
    with connect(db_path) as con:
        con.execute(
            "UPDATE videos SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
            (error[:2000], _now(), video_id),
        )


def used_topics(db_path, channel_id) -> list[str]:
    """Is channel par pehle bane hue topics (taake dobara wahi topic na chuna jaye)."""
    if channel_id is None:
        cond, params = "channel_id IS NULL", ()
    else:
        cond, params = "channel_id = ?", (channel_id,)
    with connect(db_path) as con:
        rows = con.execute(
            f"SELECT topic FROM videos WHERE {cond} AND status != 'failed' AND topic != '' ORDER BY id",
            params,
        ).fetchall()
    return [r["topic"] for r in rows]


def mark_stale_jobs(db_path) -> int:
    """Server band hone se jo jobs adhoori reh gayi thi unhe failed mark karna."""
    with connect(db_path) as con:
        return con.execute(
            "UPDATE videos SET status = 'failed', error = ?, updated_at = ? "
            "WHERE status IN ('queued', 'generating')",
            ("Server band hone se job adhoori reh gayi", _now()),
        ).rowcount


def stats(db_path) -> dict:
    with connect(db_path) as con:
        rows = con.execute("SELECT status, COUNT(*) AS n FROM videos GROUP BY status").fetchall()
    result = {r["status"]: r["n"] for r in rows}
    result["total"] = sum(result.values())
    return result


def set_channel_branding(db_path, channel_id: int, branding_json) -> bool:
    """Channel ki branding settings (JSON) likhna. None dene se branding hat jati hai."""
    with connect(db_path) as con:
        return con.execute("UPDATE channels SET branding_json = ? WHERE id = ?",
                           (branding_json, channel_id)).rowcount > 0


def set_run_dir(db_path, video_id: int, run_dir) -> None:
    """Run folder ka path likhna (fail hui video ko dobara chalane ke liye)."""
    with connect(db_path) as con:
        con.execute("UPDATE videos SET run_dir = ? WHERE id = ?", (run_dir, video_id))
