"""Variations ka API endpoint: ek topic, kai languages."""
import threading

from fastapi import HTTPException
from pydantic import BaseModel

from app.core import db
from app.services.variations import create_variation_jobs, process_variation


class VariationRequest(BaseModel):
    topic: str
    languages: list[str]


def _spawn(work) -> None:
    threading.Thread(target=work, daemon=True).start()


def register_variation_routes(app, path, runner, spawn=None) -> None:
    @app.post("/channels/{channel_id}/variations", status_code=202)
    def create_variations(channel_id: int, body: VariationRequest):
        try:
            channel, jobs = create_variation_jobs(path, channel_id, body.topic, body.languages)
        except db.NotFoundError:
            raise HTTPException(404, "Channel nahi mila")
        except ValueError as exc:
            raise HTTPException(422, str(exc))

        def work():
            for video_id, language in jobs:
                process_variation(path, runner, channel, video_id, body.topic.strip(), language)

        (spawn or _spawn)(work)
        return {"videos": [{"id": v, "language": lang} for v, lang in jobs]}
