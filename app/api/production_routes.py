"""Production schedule aur analytics ke API endpoints."""
from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.core import analytics, db, db_production
from app.core.config import settings
from app.services.gemini_client import GeminiError

VIDEO_FIELDS = ("id", "channel_id", "title", "topic", "youtube_id", "privacy", "published_at",
                "views", "likes", "comments", "stats_at")


class ScheduleSettings(BaseModel):
    daily_videos: int = Field(0, ge=0, le=db_production.MAX_DAILY)
    produce_at: str = "09:00"
    video_seconds: int = Field(40, ge=15, le=90)


def register_production_routes(app, path, auto_produce: bool, stats_fn, insights_fn) -> None:
    @app.put("/channels/{channel_id}/schedule")
    def set_schedule(channel_id: int, body: ScheduleSettings):
        try:
            return db_production.set_channel_schedule(
                path, channel_id, body.daily_videos, body.produce_at, body.video_seconds
            )
        except db.NotFoundError:
            raise HTTPException(404, "Channel nahi mila")
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @app.get("/production")
    def production():
        today = datetime.now().date().isoformat()
        rows = []
        for channel in db.list_channels(path):
            produced, failed = db_production.count_today(path, channel["id"], today)
            rows.append({
                "id": channel["id"], "name": channel["name"], "niche": channel["niche"],
                "language": channel["language"], "daily_videos": channel["daily_videos"],
                "produce_at": channel["produce_at"], "video_seconds": channel["video_seconds"],
                "produced_today": produced, "failed_today": failed,
            })
        return {"auto_produce": auto_produce, "check_minutes": settings.produce_check_minutes, "channels": rows}

    @app.post("/analytics/refresh")
    def refresh():
        return stats_fn(path)

    @app.get("/analytics")
    def get_analytics():
        videos = db_production.published_videos(path)
        return {
            "summary": analytics.summarize(videos),
            "videos": [{key: v.get(key) for key in VIDEO_FIELDS} for v in videos],
        }

    @app.post("/analytics/insights")
    def insights():
        try:
            return insights_fn(db_production.published_videos(path))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except GeminiError as exc:
            raise HTTPException(502, str(exc))
