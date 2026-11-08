"""Trend research: YouTube ke 'most popular' videos se topic ideas ka context.

videos.list(chart=mostPopular) 1 quota unit leta hai. Kuch bhi fail ho to [] (video nahi rukti).
Region badalne ke liye environment variable TRENDS_REGION (maslan PK) de sakte hain.
"""
import os
import re
from pathlib import Path

from pydantic import BaseModel

from app.services import youtube as yt

REGIONS = {"english": "US", "hindi": "IN", "urdu": "PK", "spanish": "ES", "french": "FR", "arabic": "SA"}

# (keywords, YouTube video category id)
CATEGORIES = [
    ({"science", "space", "tech", "technology", "ai", "physics", "astronomy", "gadgets", "coding", "robots"}, "28"),
    ({"gaming", "games", "gamer"}, "20"),
    ({"sports", "football", "cricket", "fitness", "soccer"}, "17"),
    ({"news", "politics"}, "25"),
    ({"education", "learning", "study", "history"}, "27"),
    ({"comedy", "funny", "memes"}, "23"),
    ({"celebrity", "entertainment"}, "24"),
    ({"howto", "diy", "tips", "beauty", "fashion", "style"}, "26"),
    ({"movies", "film", "cinema"}, "1"),
    ({"music", "songs"}, "10"),
    ({"travel"}, "19"),
    ({"pets", "animals", "dogs", "cats"}, "15"),
    ({"cars", "auto"}, "2"),
]


class TrendItem(BaseModel):
    title: str
    channel: str = ""
    views: int = 0
    category_id: str = ""


def region_for_language(language: str) -> str:
    return (os.getenv("TRENDS_REGION") or "").strip().upper() or REGIONS.get((language or "").strip().lower(), "US")


def niche_category(niche: str) -> str | None:
    tokens = set(re.findall(r"[a-z]+", (niche or "").lower()))
    for words, cid in CATEGORIES:
        if tokens & words:
            return cid
    return None


def _list(service, region, category_id, max_results):
    kw = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": region, "maxResults": max_results}
    if category_id:
        kw["videoCategoryId"] = category_id
    return service.videos().list(**kw).execute()


def fetch_trending(service, region: str = "US", category_id: str | None = None,
                   max_results: int = 25) -> list[TrendItem]:
    try:
        data = _list(service, region, category_id, max_results)
    except Exception:  # noqa: BLE001 - trends fail hon to bhi video na ruke
        return []
    items, seen = [], set()
    for v in (data or {}).get("items", []):
        sn = v.get("snippet") or {}
        title = " ".join(str(sn.get("title", "")).split())
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        try:
            views = int((v.get("statistics") or {}).get("viewCount") or 0)
        except (TypeError, ValueError):
            views = 0
        items.append(TrendItem(title=title, channel=str(sn.get("channelTitle", "")), views=views,
                               category_id=str(sn.get("categoryId", ""))))
    return items


def fetch_with_fallback(service, region: str, category_id: str | None, max_results: int = 25):
    """Pehle niche ki category, khali ya fail ho to general most popular."""
    items = fetch_trending(service, region, category_id, max_results) if category_id else []
    return items or fetch_trending(service, region, None, max_results)


def any_connected_channel(tokens_dir=None) -> str | None:
    folder = Path(tokens_dir or yt.DEFAULT_TOKENS_DIR)
    if not folder.exists():
        return None
    for f in sorted(folder.glob("youtube_*.json")):
        return f.stem.split("_", 1)[1]
    return None


def trend_titles(niche: str, language: str = "English", limit: int = 12, service=None,
                 tokens_dir=None, region: str | None = None) -> list[str]:
    """Runner ke liye: trending titles ki list. Token na ho ya kuch fail ho to []."""
    try:
        svc = service
        if svc is None:
            cid = any_connected_channel(tokens_dir)
            if cid is None:
                return []
            svc = yt.build_service(yt.load_credentials(cid, tokens_dir))
        items = fetch_with_fallback(svc, region or region_for_language(language), niche_category(niche))
        return [i.title for i in items[:limit]]
    except Exception:  # noqa: BLE001
        return []
