"""Long-form API: generate, progress, resume, approve, series."""
import json
import re
import threading
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.core import db, db_series
from app.core.config import settings
from app.services import long_pipeline as lp
from app.services.tts import pick_voice


class LongRequest(BaseModel):
    topic: str = Field(min_length=3)
    channel_id: int | None = None
    series_id: int | None = None
    language: str | None = None
    minutes: float = Field(10.0, ge=3, le=20)
    voice: str | None = None


class SeriesCreate(BaseModel):
    name: str
    channel_id: int | None = None
    narrator: str = ""
    tone: str = ""
    audience: str = ""


def _read(run, name):
    f = Path(run) / name
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except (OSError, ValueError):
        return None


def register_long_routes(app: FastAPI, path, runner=None, lock=None, output_dir=None):
    runner = runner or lp.default_long_runner
    if lock is None:
        from app.services.production import JOB_LOCK as lock
    out_root = Path(output_dir) if output_dir else Path(settings.output_dir)

    def auto_approve(video_id):
        """LONG_AUTO_APPROVE=true ho aur video 'ready' ho to approve + abhi ke liye schedule."""
        from datetime import datetime
        from app.core import db_publish
        from app.services.long_script import _raw
        if str(_raw("LONG_AUTO_APPROVE") or "").strip().lower() not in ("1", "true", "yes", "on"):
            return
        try:
            v = db.get_video(path, video_id)
            if not v or v["status"] != "ready":
                return
            db.transition(path, video_id, "approved", {"ready"})
            if v.get("series_id"):
                from app.services.long_script import LongScript
                f = Path(v["run_dir"]) / "long_script.json"
                if f.is_file():
                    db_series.save_structure(path, v["series_id"], LongScript.model_validate_json(f.read_text(encoding="utf-8")))
            db_publish.schedule_video(path, video_id, db_publish.parse_when(datetime.now().replace(microsecond=0).isoformat()))
        except Exception as exc:
            print(f"Auto-approve nahi hua: {exc}", flush=True)

    def run_job(video_id, run_dir):
        with lock:
            try:
                db.transition(path, video_id, "generating", {"queued"})
                p = _read(run_dir, "long_params.json") or {}
                style, transition = None, 0.4
                if p.get("series_id"):
                    s = db_series.get_series(path, p["series_id"])
                    style = db_series.series_style(s, p.get("episode"))
                    transition = db_series.series_transition(s)
                result = runner(topic=p["topic"], language=p["language"], minutes=p["minutes"],
                                voice=p.get("voice"), run_dir=str(run_dir), style=style, transition=transition)
                db.finish_video(path, video_id, result)
                auto_approve(video_id)
            except Exception as exc:
                db.fail_video(path, video_id, str(exc) or type(exc).__name__)

    def long_video(video_id):
        v = db.get_video(path, video_id)
        if v is None:
            raise HTTPException(404, "Video nahi mili")
        if not v["run_dir"] or _read(v["run_dir"], "long_params.json") is None:
            raise HTTPException(404, "Ye long-form video nahi hai")
        return v

    @app.post("/long/generate", status_code=202)
    def long_generate(body: LongRequest, background: BackgroundTasks):
        channel = db.get_channel(path, body.channel_id) if body.channel_id is not None else None
        if body.channel_id is not None and channel is None:
            raise HTTPException(404, "Channel nahi mila")
        language = body.language or (channel["language"] if channel else "English")
        voice = body.voice or (channel["voice"] if channel else None)
        try:
            pick_voice(language, voice)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if body.series_id is not None:
            try:
                db_series.get_series(path, body.series_id)
            except db.NotFoundError:
                raise HTTPException(404, "Series nahi mili")
        topic = " ".join(body.topic.split())
        vid = db.create_job(path, body.channel_id, topic, language)
        episode = db_series.attach_episode(path, vid, body.series_id) if body.series_id is not None else None
        slug = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")[:40] or "long"
        run = out_root / "runs" / f"{time.strftime('%Y%m%d_%H%M%S')}_{slug}"
        run.mkdir(parents=True, exist_ok=True)
        (run / "long_params.json").write_text(json.dumps(
            {"topic": topic, "language": language, "minutes": body.minutes, "voice": voice,
             "series_id": body.series_id, "episode": episode}, ensure_ascii=False), encoding="utf-8")
        lp.write_progress(run, status="queued", stage="queued", pct=0)
        db.set_run_dir(path, vid, str(run))
        background.add_task(run_job, vid, str(run))
        return {"id": vid, "status": "queued", "episode": episode}

    @app.get("/long")
    def long_list():
        rows = []
        for v in db.list_videos(path, None, None, 200):
            if v["run_dir"] and (Path(v["run_dir"]) / "long_params.json").is_file():
                pr = lp.read_progress(v["run_dir"])
                rows.append({"id": v["id"], "title": v["title"] or v["topic"], "status": v["status"],
                             "stage": pr.get("stage"), "pct": pr.get("pct", 0)})
        return rows

    @app.get("/videos/{video_id}/long")
    def long_detail(video_id: int):
        v = long_video(video_id)
        r = v["run_dir"]
        return {"id": video_id, "status": v["status"], "error": v["error"], "series_id": v.get("series_id"),
                "episode_no": v.get("episode_no"), "params": _read(r, "long_params.json"),
                "progress": lp.read_progress(r), "package": _read(r, "long_package.json"),
                "quality": _read(r, "long_quality.json")}

    @app.post("/videos/{video_id}/long/resume", status_code=202)
    def long_resume(video_id: int, background: BackgroundTasks):
        v = long_video(video_id)
        try:
            db.transition(path, video_id, "queued", {"failed", "needs_review", "ready"})
        except db.InvalidTransitionError as exc:
            raise HTTPException(409, str(exc))
        lp.write_progress(v["run_dir"], status="queued", error=None)
        background.add_task(run_job, video_id, v["run_dir"])
        return {"id": video_id, "status": "queued"}

    @app.post("/videos/{video_id}/long/approve")
    def long_approve(video_id: int):
        v = long_video(video_id)
        try:
            row = db.transition(path, video_id, "approved", {"ready", "needs_review"})
        except db.InvalidTransitionError as exc:
            raise HTTPException(409, str(exc))
        if v.get("series_id"):
            from app.services.long_script import LongScript
            f = Path(v["run_dir"]) / "long_script.json"
            if f.is_file():
                db_series.save_structure(path, v["series_id"], LongScript.model_validate_json(f.read_text(encoding="utf-8")))
        return {"id": video_id, "status": row["status"]}

    @app.get("/series")
    def series_list(channel_id: int | None = None):
        return db_series.list_series(path, channel_id)

    @app.post("/series", status_code=201)
    def series_create(body: SeriesCreate):
        try:
            return db_series.create_series(path, body.name, body.channel_id, body.narrator, body.tone, body.audience)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
