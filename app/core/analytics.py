"""Analytics ka hisaab (bina network ke)."""


def engagement_rate(views, likes, comments) -> float:
    return round((likes + comments) / views, 4) if views else 0.0


def summarize(videos: list[dict]) -> dict:
    rows = [v for v in videos if v.get("views") is not None]
    if not rows:
        return {"videos": 0, "total_views": 0, "avg_views": 0, "engagement": 0.0, "best": None}
    total = sum(v["views"] for v in rows)
    likes = sum(v.get("likes") or 0 for v in rows)
    comments = sum(v.get("comments") or 0 for v in rows)
    best = max(rows, key=lambda v: v["views"])
    return {
        "videos": len(rows),
        "total_views": total,
        "avg_views": round(total / len(rows), 1),
        "engagement": engagement_rate(total, likes, comments),
        "best": {"id": best["id"], "title": best.get("title") or best.get("topic"), "views": best["views"]},
    }
