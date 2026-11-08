"""Production aur analytics pages ke helper functions."""


def format_count(n) -> str:
    if n is None:
        return "-"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def engagement_text(rate) -> str:
    return f"{(rate or 0) * 100:.1f}%"


def schedule_summary(channel: dict) -> str:
    if not channel["daily_videos"]:
        return "Band"
    return f"Roz {channel['daily_videos']} videos, {channel['produce_at']} ke baad, {channel['video_seconds']}s"


def analytics_rows(videos: list[dict]) -> list[dict]:
    rows = []
    for v in videos:
        views = v.get("views")
        engagement = "-" if not views else engagement_text(((v.get("likes") or 0) + (v.get("comments") or 0)) / views)
        rows.append({
            "ID": v["id"],
            "Title": v.get("title") or v.get("topic") or "-",
            "Views": format_count(views),
            "Likes": format_count(v.get("likes")),
            "Comments": format_count(v.get("comments")),
            "Engagement": engagement,
            "Updated": (v.get("stats_at") or "-").replace("T", " "),
        })
    return rows


def refresh_message(summary: dict) -> str:
    parts = [f"{summary['updated']} videos ke stats update hue"]
    for channel_id in summary.get("needs_reconnect", []):
        parts.append(
            f"Channel {channel_id} ko dobara connect karein (naya permission chahiye): "
            f"python -m scripts.connect_youtube {channel_id}"
        )
    parts.extend(summary.get("errors", []))
    return " | ".join(parts)
