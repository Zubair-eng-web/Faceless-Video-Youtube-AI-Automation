"""YouTube se views/likes/comments lena (youtube.readonly permission chahiye)."""
import json

from googleapiclient.errors import HttpError

from app.core import db_production
from app.services import youtube as yt


def token_scopes(channel_id, tokens_dir=None) -> set:
    path = yt.token_path(channel_id, tokens_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    scopes = data.get("scopes") or []
    if isinstance(scopes, str):
        scopes = scopes.split()
    return set(scopes)


def fetch_stats(service, youtube_ids, batch_size: int = 50) -> dict:
    ids = list(dict.fromkeys(youtube_ids))
    result: dict = {}
    for start in range(0, len(ids), batch_size):
        batch = ids[start:start + batch_size]
        try:
            response = service.videos().list(part="statistics", id=",".join(batch)).execute()
        except HttpError as exc:
            raise yt._translate(exc) from exc
        for item in response.get("items", []):
            stats = item.get("statistics", {})
            result[item["id"]] = {
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
            }
    return result


def _default_service(channel_id):
    return yt.build_service(yt.load_credentials(channel_id))


def refresh_stats(db_path, service_factory=_default_service, tokens_dir=None) -> dict:
    summary = {"updated": 0, "needs_reconnect": [], "errors": []}
    by_channel: dict = {}
    for video in db_production.published_with_youtube_id(db_path):
        if video["channel_id"] is not None:
            by_channel.setdefault(video["channel_id"], []).append(video)

    for channel_id, videos in by_channel.items():
        if yt.SCOPE_READONLY not in token_scopes(channel_id, tokens_dir):
            summary["needs_reconnect"].append(channel_id)
            continue
        try:
            service = service_factory(channel_id)
            stats = fetch_stats(service, [v["youtube_id"] for v in videos])
        except yt.YouTubeError as exc:
            summary["errors"].append(f"Channel {channel_id}: {exc}")
            continue
        for video in videos:
            numbers = stats.get(video["youtube_id"])
            if numbers:
                db_production.update_video_stats(
                    db_path, video["id"], numbers["views"], numbers["likes"], numbers["comments"]
                )
                summary["updated"] += 1
    return summary
