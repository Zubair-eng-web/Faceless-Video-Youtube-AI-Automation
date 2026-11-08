"""Background jobs ki list: publish aur production."""
from app.core.config import settings
from app.services.production import produce_due
from app.services.scheduler import Job


def build_jobs(db_path, runner, publish_job, publish_enabled: bool, produce_enabled: bool) -> list:
    return [
        Job("publish", publish_job, settings.publish_check_minutes, publish_enabled),
        Job("produce", lambda: produce_due(db_path, runner), settings.produce_check_minutes, produce_enabled),
    ]
