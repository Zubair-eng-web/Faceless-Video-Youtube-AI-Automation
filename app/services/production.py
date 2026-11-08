"""Production schedule: channel ke hisab se roz khud videos banwana."""
import threading
from datetime import datetime

from app.core import db, db_production

JOB_LOCK = threading.Lock()  # ek waqt me ek hi video banti hai (free API limits ke liye)
MAX_FAILED_PER_DAY = 2


def _branding_kwargs(db_path, channel) -> dict:
    """Channel ki branding (agar set ho) runner ko dene ke liye."""
    from app.services.branding import branding_from_row
    b = branding_from_row(db.get_channel(db_path, channel["id"]))
    return {"branding": b} if b else {}


def run_one(db_path, runner, channel, lock=JOB_LOCK) -> int:
    video_id = db.create_job(db_path, channel["id"], "", channel["language"])
    with lock:
        try:
            db.transition(db_path, video_id, "generating", {"queued"})
            used = db.used_topics(db_path, channel["id"])
            result = runner(
                topic=None, niche=channel["niche"], language=channel["language"],
                seconds=channel["video_seconds"], voice=channel["voice"], used_topics=used, **_branding_kwargs(db_path, channel),
            )
            db.finish_video(db_path, video_id, result)
        except Exception as exc:
            db.fail_video(db_path, video_id, str(exc) or type(exc).__name__)
    return video_id


def produce_due(db_path, runner, now=datetime.now, lock=JOB_LOCK) -> list[int]:
    """Jin channels ka waqt aa chuka aur aaj ka kota baqi hai, un ki ek ek video banata hai."""
    current = now()
    clock = current.strftime("%H:%M")
    day = current.date().isoformat()
    made: list[int] = []
    for channel in db_production.scheduled_channels(db_path):
        if not channel["niche"].strip():
            continue
        if clock < channel["produce_at"]:
            continue
        produced, failed = db_production.count_today(db_path, channel["id"], day)
        if produced >= channel["daily_videos"] or failed >= MAX_FAILED_PER_DAY:
            continue
        made.append(run_one(db_path, runner, channel, lock))
    return made
