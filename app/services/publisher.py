"""Approved videos ko YouTube par bhejna: ek video ya jo schedule par tayyar hon."""
import threading
from datetime import datetime, timedelta
from pathlib import Path

from app.agents.seo_agent import SEOPack
from app.core import db, db_publish
from app.services.youtube import YouTubeQuotaError, upload_to_youtube

UPLOAD_LOCK = threading.Lock()  # ek waqt me ek hi upload
QUOTA_STATE = {"until": None}   # quota khatam hone par kuch der ke liye ruk jana
QUOTA_PAUSE = timedelta(hours=1)


class PublishError(RuntimeError):
    pass


def prepare_publish(db_path, video_id: int) -> dict:
    """Jaanch karke video ko 'publishing' mark karta hai. Masla ho to status nahi badalta."""
    video = db.get_video(db_path, video_id)
    if video is None:
        raise db.NotFoundError(f"Video {video_id} nahi mili")
    if video["status"] != "approved":
        raise db.InvalidTransitionError(video["status"], "publishing")
    if video["channel_id"] is None:
        raise PublishError("Is video ka channel nahi hai, isliye YouTube par nahi ja sakti")
    if not video["video_path"] or not Path(video["video_path"]).exists():
        raise PublishError("Video file disk par nahi mili")
    if not video["seo_json"]:
        raise PublishError("Video ka SEO data nahi hai")
    return db_publish.claim_for_publish(db_path, video_id)


def execute_publish(db_path, video: dict, uploader=upload_to_youtube, privacy: str = "private") -> dict:
    """Upload karta hai aur nateeja database me likhta hai. Fail hone par error dobara uthata hai."""
    with UPLOAD_LOCK:
        try:
            pack = SEOPack.model_validate_json(video["seo_json"])
            outcome = uploader(
                video["channel_id"], video["video_path"], pack.title, pack.full_description, pack.tags,
                thumbnail_path=video["thumbnail_path"], privacy=privacy,
            )
        except YouTubeQuotaError:
            db_publish.release_publish(
                db_path, video["id"],
                "YouTube ki roz ki limit khatam. Thori der baad khud dobara koshish hogi ya 'Abhi publish karein' dabayen.",
            )
            raise
        except Exception as exc:
            db_publish.fail_publish(db_path, video["id"], str(exc) or type(exc).__name__)
            raise
        note = f"Thumbnail nahi lagi: {outcome['thumbnail_error']}" if outcome.get("thumbnail_error") else None
        db_publish.finish_publish(db_path, video["id"], outcome["video_id"], privacy, note)
    return db.get_video(db_path, video["id"])


def run_publish(db_path, video: dict, uploader=upload_to_youtube, privacy: str = "private") -> None:
    """Background task ke liye: error nahi uthata (nateeja database me likha jata hai)."""
    try:
        execute_publish(db_path, video, uploader, privacy)
    except Exception:
        pass


def publish_due(db_path, uploader=upload_to_youtube, daily_limit: int = 5, privacy: str = "private",
                now=datetime.now) -> list[int]:
    """Jin approved videos ka schedule ka waqt aa chuka hai unhe upload karta hai. Uploaded ids wapas deta hai."""
    current = now()
    until = QUOTA_STATE["until"]
    if until is not None:
        if current < until:
            return []
        QUOTA_STATE["until"] = None

    remaining = daily_limit - db_publish.published_today(db_path, current.date().isoformat())
    if remaining <= 0:
        return []

    done: list[int] = []
    for video in db_publish.due_videos(db_path, current.replace(microsecond=0).isoformat(), limit=remaining):
        try:
            claimed = prepare_publish(db_path, video["id"])
        except PublishError as exc:
            db_publish.fail_publish(db_path, video["id"], str(exc))
            continue
        except db.InvalidTransitionError:
            continue
        try:
            execute_publish(db_path, claimed, uploader, privacy)
            done.append(video["id"])
        except YouTubeQuotaError:
            QUOTA_STATE["until"] = current + QUOTA_PAUSE
            break
        except Exception:
            continue  # error database me likha ja chuka hai
    return done
