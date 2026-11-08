"""Publish ke API endpoints."""
from datetime import datetime

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core import db, db_publish
from app.core.config import settings
from app.services.publisher import PublishError, prepare_publish, run_publish
from app.services.youtube import is_connected


class ScheduleRequest(BaseModel):
    when: str


def register_publish_routes(app, path, uploader, video_out, auto_publish: bool) -> None:
    def guarded(fn, *args):
        try:
            return fn(*args)
        except db.NotFoundError:
            raise HTTPException(404, "Video nahi mili")
        except db.InvalidTransitionError as exc:
            raise HTTPException(409, str(exc))
        except (PublishError, ValueError) as exc:
            raise HTTPException(422, str(exc))

    @app.post("/videos/{video_id}/publish", status_code=202)
    def publish(video_id: int, background: BackgroundTasks):
        video = guarded(prepare_publish, path, video_id)
        background.add_task(run_publish, path, video, uploader, settings.default_privacy)
        return video_out(video)

    @app.post("/videos/{video_id}/schedule")
    def schedule(video_id: int, body: ScheduleRequest):
        return video_out(guarded(db_publish.schedule_video, path, video_id, body.when))

    @app.post("/videos/{video_id}/unschedule")
    def unschedule(video_id: int):
        return video_out(guarded(db_publish.unschedule_video, path, video_id))

    @app.post("/videos/{video_id}/retry-publish")
    def retry_publish(video_id: int):
        return video_out(guarded(db_publish.retry_publish, path, video_id))

    @app.get("/youtube/channels")
    def youtube_channels():
        return [
            {"id": c["id"], "name": c["name"], "connected": is_connected(c["id"])}
            for c in db.list_channels(path)
        ]

    @app.get("/publishing")
    def publishing_info():
        today = datetime.now().date().isoformat()
        return {
            "auto_publish": auto_publish,
            "privacy": settings.default_privacy,
            "daily_limit": settings.daily_upload_limit,
            "check_minutes": settings.publish_check_minutes,
            "published_today": db_publish.published_today(path, today),
        }
