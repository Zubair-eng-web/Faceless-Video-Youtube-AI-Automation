"""Dashboard ke chhote helper functions (UI se alag, taake test ho saken)."""
from datetime import date, datetime, time

STATUSES = ["queued", "generating", "ready", "needs_review", "approved", "publishing", "published",
            "publish_failed", "rejected", "failed"]
ACTIVE = {"queued", "generating", "publishing"}
REVIEWABLE = {"ready", "needs_review"}
HAS_FILES = {"ready", "needs_review", "approved", "rejected", "publishing", "published", "publish_failed"}

LABELS = {
    "queued": "\u23F3 queued",
    "generating": "\u2699 generating",
    "ready": "\u2705 ready",
    "needs_review": "\u26A0 needs review",
    "approved": "\U0001F44D approved",
    "publishing": "\u2B06 publishing",
    "published": "\U0001F680 published",
    "publish_failed": "\U0001F6A8 publish failed",
    "rejected": "\u274C rejected",
    "failed": "\U0001F6A8 failed",
}


def status_label(status: str) -> str:
    return LABELS.get(status, status)


def format_duration(seconds) -> str:
    return "-" if not seconds else f"{seconds:.1f}s"


def is_active(video: dict) -> bool:
    return video["status"] in ACTIVE


def can_approve(status: str) -> bool:
    return status in REVIEWABLE


def can_reject(status: str) -> bool:
    return status in REVIEWABLE or status == "approved"


def can_publish(status: str) -> bool:
    return status == "approved"


def can_retry_publish(status: str) -> bool:
    return status == "publish_failed"


def schedule_text(video: dict):
    when = video.get("scheduled_at")
    return when.replace("T", " ")[:16] if when else None


def youtube_link(video: dict):
    video_id = video.get("youtube_id")
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else None


def combine_when(day: date, at: time) -> str:
    return datetime.combine(day, at).replace(second=0, microsecond=0).isoformat()


def video_label(video: dict) -> str:
    name = video["title"] or video["topic"] or "naya video"
    return f"#{video['id']} - {name} [{video['status']}]"


def video_rows(videos: list[dict], channel_names: dict) -> list[dict]:
    return [
        {
            "ID": v["id"],
            "Channel": channel_names.get(v["channel_id"], "-"),
            "Title": v["title"] or v["topic"] or "(topic chuna ja raha hai)",
            "Status": status_label(v["status"]),
            "Duration": format_duration(v["duration"]),
            "Created": v["created_at"].replace("T", " "),
        }
        for v in videos
    ]


def channel_options(channels: list[dict]) -> dict:
    return {f"{c['name']} (id {c['id']})": c["id"] for c in channels}


def quality_summary(quality) -> tuple[str, list[str]]:
    if not quality:
        return "-", []
    issues = quality.get("issues", [])
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    verdict = "FAIL" if errors else "PASS"
    headline = f"{verdict} ({len(errors)} errors, {len(warnings)} warnings)"
    lines = [f"[{i['level'].upper()}] {i.get('code') or i.get('area', '')}: {i.get('message') or i.get('msg', '')}"
             + (f" -> {i['fix']}" if i.get('fix') else "") for i in issues]
    return headline, lines


def description_text(seo: dict) -> str:
    return seo["description"] + "\n\n" + " ".join(seo["hashtags"])
