"""FastAPI backend: channels, videos aur video generation jobs."""
import json
import threading
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.runner import default_runner
from app.api.schemas import ChannelCreate, GenerateRequest
from app.services.branding import Branding, branding_from_row
from app.services.redo import RedoRequest, default_redo, load_storyboard_view
from app.services import api_key as api_key_mod
from app import pipeline as pipeline_mod
from app.core import db
from app.core.config import settings
from app.api.publish_routes import register_publish_routes
from app.core import db_publish
from app.services.publisher import publish_due
from app.agents.insights_agent import insights_from_videos
from app.api.production_routes import register_production_routes
from app.api.variation_routes import register_variation_routes
from app.api.long_routes import register_long_routes
from app.services.background import build_jobs
from app.services.production import JOB_LOCK
from app.services.scheduler import make_multi_lifespan
from app.services.youtube_stats import refresh_stats
from app.services.tts import pick_voice
from app.services.youtube import upload_to_youtube

VIDEO_FIELDS = ("id", "channel_id", "topic", "language", "status", "title", "duration",
                "error", "run_dir", "created_at", "updated_at", "youtube_id", "privacy",
                "scheduled_at", "published_at", "publish_error")
REVIEWABLE = {"ready", "needs_review"}


def load_fact_check(run_dir):
    """Run folder se fact_check.json parhna (nahi mili ya kharab ho to None)."""
    if not run_dir:
        return None
    f = Path(run_dir) / "fact_check.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except (OSError, ValueError):
        return None


def video_out(row: dict) -> dict:
    out = {key: row[key] for key in VIDEO_FIELDS}
    out["seo"] = json.loads(row["seo_json"]) if row["seo_json"] else None
    out["quality"] = json.loads(row["quality_json"]) if row["quality_json"] else None
    out["fact_check"] = load_fact_check(row["run_dir"])
    return out


def create_app(db_path=None, runner=None, uploader=None, auto_publish=None,
               stats_fn=None, insights_fn=None, auto_produce=None, redoer=None) -> FastAPI:
    path = Path(db_path) if db_path else settings.db_path
    db.init_db(path)
    db.mark_stale_jobs(path)
    db_publish.mark_stale_publishes(path)
    run = runner or default_runner
    lock = JOB_LOCK  # ek waqt me ek hi video (free API limits ke liye)

    upload = uploader or upload_to_youtube
    enabled = settings.auto_publish if auto_publish is None else auto_publish
    produce_enabled = settings.auto_produce if auto_produce is None else auto_produce

    def publish_job():
        publish_due(path, upload, daily_limit=settings.daily_upload_limit, privacy=settings.default_privacy)

    app = FastAPI(title="Faceless Video AI",
                  lifespan=make_multi_lifespan(build_jobs(path, run, publish_job, enabled, produce_enabled)))

    def run_job(video_id, channel_id, topic, niche, language, seconds, voice, branding=None):
        with lock:
            try:
                db.transition(path, video_id, "generating", {"queued"})
                pipeline_mod.LAST_RUN_DIR = None
                used = db.used_topics(path, channel_id)
                result = run(topic=topic, niche=niche, language=language, seconds=seconds,
                             voice=voice, used_topics=used, **({"branding": branding} if branding else {}))
                db.finish_video(path, video_id, result)
            except Exception as exc:
                db.fail_video(path, video_id, str(exc) or type(exc).__name__)
                if pipeline_mod.LAST_RUN_DIR:
                    db.set_run_dir(path, video_id, pipeline_mod.LAST_RUN_DIR)

    def video_or_404(video_id: int) -> dict:
        video = db.get_video(path, video_id)
        if video is None:
            raise HTTPException(404, "Video nahi mili")
        return video

    def change_status(video_id: int, new_status: str, allowed) -> dict:
        try:
            return video_out(db.transition(path, video_id, new_status, allowed))
        except db.NotFoundError:
            raise HTTPException(404, "Video nahi mili")
        except db.InvalidTransitionError as exc:
            raise HTTPException(409, str(exc))

    @app.get("/settings/gemini")
    def gemini_key_status(force: bool = False):
        return api_key_mod.get_status(force=force)

    @app.post("/settings/gemini")
    def gemini_key_set(body: api_key_mod.KeyBody):
        try:
            return api_key_mod.set_key(body.key)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/stats")
    def get_stats():
        return db.stats(path)

    # ---------- Channels ----------
    @app.post("/channels", status_code=201)
    def create_channel(body: ChannelCreate):
        try:
            pick_voice(body.language, body.voice)
            return db.create_channel(path, body.name, body.niche, body.language, body.voice)
        except db.DuplicateChannelError as exc:
            raise HTTPException(409, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @app.get("/channels")
    def list_channels():
        return db.list_channels(path)

    @app.get("/channels/{channel_id}")
    def get_channel(channel_id: int):
        channel = db.get_channel(path, channel_id)
        if channel is None:
            raise HTTPException(404, "Channel nahi mila")
        return channel

    @app.get("/channels/{channel_id}/branding")
    def get_branding(channel_id: int):
        channel = db.get_channel(path, channel_id)
        if channel is None:
            raise HTTPException(404, "Channel nahi mila")
        return (branding_from_row(channel) or Branding()).model_dump()

    @app.put("/channels/{channel_id}/branding")
    def put_branding(channel_id: int, body: Branding):
        if not db.set_channel_branding(path, channel_id, body.model_dump_json()):
            raise HTTPException(404, "Channel nahi mila")
        return body.model_dump()

    redo_fn = redoer or default_redo

    def run_redo_job(video_id, run_dir, edits, branding):
        with lock:
            try:
                db.transition(path, video_id, "generating", {"queued"})
                result = redo_fn(run_dir=run_dir, edits=edits, branding=branding)
                db.finish_video(path, video_id, result)
            except Exception as exc:
                db.fail_video(path, video_id, str(exc) or type(exc).__name__)

    @app.get("/videos/{video_id}/storyboard")
    def get_storyboard(video_id: int):
        video = video_or_404(video_id)
        view = load_storyboard_view(video["run_dir"])
        if view is None:
            raise HTTPException(404, "Is video ka script folder nahi mila")
        return view

    @app.post("/videos/{video_id}/redo", status_code=202)
    def redo_video(video_id: int, body: RedoRequest, background: BackgroundTasks):
        video = video_or_404(video_id)
        run_dir = video["run_dir"]
        if load_storyboard_view(run_dir) is None:
            raise HTTPException(400, "Is video ka script folder nahi mila, Generate se nayi video banayein")
        try:
            db.transition(path, video_id, "queued", {"ready", "needs_review", "failed"})
        except db.InvalidTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc
        channel = db.get_channel(path, video["channel_id"]) if video["channel_id"] else None
        branding = branding_from_row(channel) if channel else None
        background.add_task(run_redo_job, video_id, run_dir, body.edits, branding)
        return {"id": video_id, "status": "queued"}

    @app.delete("/channels/{channel_id}")
    def delete_channel(channel_id: int):
        if not db.delete_channel(path, channel_id):
            raise HTTPException(404, "Channel nahi mila")
        return {"deleted": True}

    # ---------- Videos ----------
    @app.post("/generate", status_code=202)
    def generate(body: GenerateRequest, background: BackgroundTasks):
        channel = None
        if body.channel_id is not None:
            channel = db.get_channel(path, body.channel_id)
            if channel is None:
                raise HTTPException(404, "Channel nahi mila")
        topic = (body.topic or "").strip() or None
        niche = (body.niche or (channel["niche"] if channel else "") or "").strip()
        language = body.language or (channel["language"] if channel else "English")
        voice = body.voice or (channel["voice"] if channel else None)
        if not topic and not niche:
            raise HTTPException(422, "Topic ya niche (ya niche wala channel) dena zaroori hai")
        try:
            pick_voice(language, voice)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        video_id = db.create_job(path, body.channel_id, topic or "", language)
        background.add_task(run_job, video_id, body.channel_id, topic, niche, language, body.seconds, voice,
                            branding_from_row(channel) if channel else None)
        return {"id": video_id, "status": "queued"}

    @app.get("/videos")
    def list_videos(status: str | None = None, channel_id: int | None = None,
                    limit: int = Query(50, ge=1, le=200)):
        return [video_out(v) for v in db.list_videos(path, status, channel_id, limit)]

    @app.get("/videos/{video_id}")
    def get_video(video_id: int):
        return video_out(video_or_404(video_id))

    @app.post("/videos/{video_id}/approve")
    def approve(video_id: int):
        return change_status(video_id, "approved", REVIEWABLE)

    @app.post("/videos/{video_id}/reject")
    def reject(video_id: int):
        return change_status(video_id, "rejected", REVIEWABLE | {"approved"})

    @app.get("/videos/{video_id}/file")
    def video_file(video_id: int):
        video = video_or_404(video_id)
        if not video["video_path"] or not Path(video["video_path"]).exists():
            raise HTTPException(404, "Video file nahi mili")
        return FileResponse(video["video_path"], media_type="video/mp4")

    @app.get("/videos/{video_id}/thumbnail")
    def video_thumbnail(video_id: int):
        video = video_or_404(video_id)
        if not video["thumbnail_path"] or not Path(video["thumbnail_path"]).exists():
            raise HTTPException(404, "Thumbnail nahi mila")
        return FileResponse(video["thumbnail_path"], media_type="image/jpeg")

    register_publish_routes(app, path, upload, video_out, enabled)
    register_production_routes(app, path, produce_enabled, stats_fn or refresh_stats,
                               insights_fn or insights_from_videos)
    register_variation_routes(app, path, run)
    register_long_routes(app, path)

    return app
