"""Ek topic ki kai languages me videos (multi-language / variations)."""
from app.core import db
from app.services.production import JOB_LOCK

MAX_LANGUAGES = 5


def clean_languages(languages) -> list[str]:
    result: list[str] = []
    for lang in languages or []:
        lang = (lang or "").strip()
        if lang and lang.lower() not in [r.lower() for r in result]:
            result.append(lang)
    if not result:
        raise ValueError("Kam az kam ek language likhein")
    if len(result) > MAX_LANGUAGES:
        raise ValueError(f"Ek baar me zyada se zyada {MAX_LANGUAGES} languages")
    return result


def create_variation_jobs(db_path, channel_id: int, topic: str, languages):
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("Topic likhein")
    langs = clean_languages(languages)
    channel = next((c for c in db.list_channels(db_path) if c["id"] == channel_id), None)
    if channel is None:
        raise db.NotFoundError(f"Channel {channel_id} nahi mila")
    jobs = [(db.create_job(db_path, channel_id, topic, lang), lang) for lang in langs]
    return channel, jobs


def process_variation(db_path, runner, channel, video_id: int, topic: str, language: str, lock=JOB_LOCK) -> None:
    with lock:
        try:
            db.transition(db_path, video_id, "generating", {"queued"})
            result = runner(
                topic=topic, niche=channel["niche"], language=language,
                seconds=channel["video_seconds"], voice=None, used_topics=[],
            )
            db.finish_video(db_path, video_id, result)
        except Exception as exc:
            db.fail_video(db_path, video_id, str(exc) or type(exc).__name__)
