"""YouTube series continuity: series, episodes, style aur structure ka reuse."""
import json
from datetime import datetime, timezone

from app.core.db import NotFoundError, connect
from app.services.long_script import SeriesStyle

DEFAULT_VISUAL = {"transition": 0.4}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(row) -> dict:
    d = dict(row)
    d["visual"] = json.loads(d.pop("visual_json") or "null") or dict(DEFAULT_VISUAL)
    d["structure"] = json.loads(d.pop("structure_json") or "null")
    return d


def create_series(db_path, name: str, channel_id=None, narrator: str = "", tone: str = "",
                  audience: str = "", visual: dict | None = None) -> dict:
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("Series ka naam khali hai")
    d = SeriesStyle()
    with connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO series (channel_id, name, narrator, tone, audience, visual_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (channel_id, name, narrator or d.narrator, tone or d.tone, audience or d.audience,
             json.dumps({**DEFAULT_VISUAL, **(visual or {})}), _now()))
        sid = cur.lastrowid
    return get_series(db_path, sid)


def get_series(db_path, series_id: int) -> dict:
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Series {series_id} nahi mili")
    return _row(row)


def list_series(db_path, channel_id=None) -> list[dict]:
    sql, args = "SELECT * FROM series", ()
    if channel_id is not None:
        sql, args = sql + " WHERE channel_id = ?", (channel_id,)
    with connect(db_path) as con:
        return [_row(r) for r in con.execute(sql + " ORDER BY id", args).fetchall()]


def next_episode_no(db_path, series_id: int) -> int:
    with connect(db_path) as con:
        n = con.execute("SELECT COALESCE(MAX(episode_no), 0) FROM videos WHERE series_id = ?",
                        (series_id,)).fetchone()[0]
    return n + 1


def attach_episode(db_path, video_id: int, series_id: int) -> int:
    """Video ko series ki agli episode bana dena; episode number wapas deta hai."""
    get_series(db_path, series_id)
    no = next_episode_no(db_path, series_id)
    with connect(db_path) as con:
        con.execute("UPDATE videos SET series_id = ?, episode_no = ? WHERE id = ?", (series_id, no, video_id))
    return no


def structure_from_script(script) -> dict:
    ch = script.chapters
    return {"chapters": len(ch), "chapter_words": round(sum(c.words for c in ch) / max(len(ch), 1)),
            "minutes": script.minutes, "titles": [c.title for c in ch][:12]}


def save_structure(db_path, series_id: int, script) -> dict:
    """Approved episode ka structure series mein rakhna (agli episode isi par chalegi)."""
    st = structure_from_script(script)
    with connect(db_path) as con:
        con.execute("UPDATE series SET structure_json = ? WHERE id = ?", (json.dumps(st, ensure_ascii=False), series_id))
    return st


def structure_note(structure: dict | None) -> str:
    if not structure:
        return ""
    return (f"Keep the same episode structure as before: a hook, then about {structure['chapters']} chapters of "
            f"roughly {structure['chapter_words']} words each, ending with a short conclusion.")


def series_style(series: dict, episode: int | None = None) -> SeriesStyle:
    note = structure_note(series.get("structure"))
    tone = (series["tone"] + (". " + note if note else "")).strip()
    return SeriesStyle(name=series["name"], narrator=series["narrator"], tone=tone,
                       audience=series["audience"], episode=episode)


def series_transition(series: dict) -> float:
    return float(series["visual"].get("transition", DEFAULT_VISUAL["transition"]))
