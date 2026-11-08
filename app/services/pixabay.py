"""Pixabay se stock video: search, behtareen clip chunna, cache ke saath download."""
import hashlib
import json
import re
import time
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.models import Storyboard

API_URL = "https://pixabay.com/api/videos/"
TARGET_SHORT_SIDE = 1080
SEARCH_CACHE_SECONDS = 24 * 3600
VARIANT_ORDER = ("large", "medium", "small", "tiny")


class PixabayError(RuntimeError):
    pass


class ClipCandidate(BaseModel):
    id: int
    page_url: str
    tags: str
    duration: float
    url: str
    width: int
    height: int
    author: str = ""

    @property
    def is_portrait(self) -> bool:
        return self.height > self.width


class SceneClip(BaseModel):
    scene_number: int
    clip_id: int
    path: str
    query: str
    width: int
    height: int
    duration: float
    portrait: bool
    page_url: str
    author: str = ""
    provider: str = "Pixabay"
    license: str = "Pixabay License"


def parse_hit(hit: dict) -> ClipCandidate | None:
    """Ek search result se sahi quality ka variant chunna.
    Jis variant ka chhota side kam az kam 1080 ho, un me se sab se chhota (4K se bachne ke liye).
    Agar koi itna bara na ho to sab se bara."""
    if "id" not in hit:
        return None
    variants = []
    for name in VARIANT_ORDER:
        v = (hit.get("videos") or {}).get(name) or {}
        url = v.get("url") or ""
        w, h = int(v.get("width") or 0), int(v.get("height") or 0)
        if url and w > 0 and h > 0:
            variants.append((url, w, h))
    if not variants:
        return None
    big_enough = [x for x in variants if min(x[1], x[2]) >= TARGET_SHORT_SIDE]
    if big_enough:
        url, w, h = min(big_enough, key=lambda x: x[1] * x[2])
    else:
        url, w, h = max(variants, key=lambda x: x[1] * x[2])
    return ClipCandidate(
        id=int(hit["id"]),
        page_url=hit.get("pageURL", ""),
        tags=hit.get("tags", ""),
        duration=float(hit.get("duration") or 0),
        url=url,
        width=w,
        height=h,
        author=str(hit.get("user") or ""),
    )


def _cache_file(cache_dir: Path, query: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:40] or "query"
    digest = hashlib.sha1(query.lower().encode("utf-8")).hexdigest()[:8]
    return Path(cache_dir) / "pixabay_search" / f"{slug}_{digest}.json"


def _fetch_search(client, key, query, per_page, max_attempts, sleep) -> dict:
    params = {"key": key, "q": query, "video_type": "all", "per_page": per_page, "safesearch": "true"}
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.get(API_URL, params=params)
        except httpx.HTTPError as exc:
            last_error = exc
        else:
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    last_error = exc
            elif response.status_code in (400, 401, 403):
                raise PixabayError(f"Pixabay ne request reject ki ({response.status_code}): {response.text[:200]}")
            else:
                last_error = PixabayError(f"HTTP {response.status_code}")
        if attempt < max_attempts:
            sleep(5.0 * attempt)
    raise PixabayError(f"Pixabay {max_attempts} koshish ke baad bhi fail: {last_error}")


def search_videos(
    query: str,
    client: httpx.Client,
    api_key: str | None = None,
    cache_dir=None,
    per_page: int = 20,
    max_attempts: int = 3,
    sleep=time.sleep,
    now=time.time,
) -> list[ClipCandidate]:
    key = api_key or settings.pixabay_api_key
    if not key:
        raise PixabayError("PIXABAY_API_KEY .env me nahi mili")
    query = " ".join(query.split())[:100]
    if not query:
        return []

    cache_file = _cache_file(Path(cache_dir or settings.cache_dir), query)
    data = None
    if cache_file.exists() and now() - cache_file.stat().st_mtime < SEARCH_CACHE_SECONDS:
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
        except ValueError:
            data = None
    if data is None:
        data = _fetch_search(client, key, query, per_page, max_attempts, sleep)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data), encoding="utf-8")

    candidates = []
    for hit in data.get("hits", []):
        parsed = parse_hit(hit)
        if parsed:
            candidates.append(parsed)
    return candidates


def score(candidate: ClipCandidate, needed_seconds: float) -> float:
    s = 0.0
    if candidate.is_portrait:
        s += 100
    if candidate.duration >= needed_seconds:
        s += 20
    else:
        s -= (needed_seconds - candidate.duration) * 2
    if min(candidate.width, candidate.height) >= TARGET_SHORT_SIDE:
        s += 10
    return s


def pick_best(candidates: list[ClipCandidate], needed_seconds: float, used=()) -> ClipCandidate | None:
    pool = [c for c in candidates if c.id not in used]
    if not pool:
        return None
    return max(pool, key=lambda c: score(c, needed_seconds))  # barabar score par pehla (zyada relevant)


def query_options(query: str, title: str) -> list[str]:
    """Pehle poori query, phir pehle 2 lafz, phir video ka title."""
    options: list[str] = []
    for q in (query, " ".join(query.split()[:2]), title):
        q = " ".join(q.split())
        if q and q not in options:
            options.append(q)
    return options


def download_clip(candidate: ClipCandidate, client: httpx.Client, cache_dir=None,
                  max_attempts: int = 3, sleep=time.sleep) -> Path:
    folder = Path(cache_dir or settings.cache_dir) / "clips"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"pixabay_{candidate.id}.mp4"
    if path.exists() and path.stat().st_size > 0:
        return path

    tmp = path.with_suffix(".part")
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            with client.stream("GET", candidate.url, follow_redirects=True) as response:
                response.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
            if tmp.stat().st_size == 0:
                raise PixabayError("Download ki hui file khali hai")
            tmp.replace(path)
            return path
        except Exception as exc:
            last_error = exc
            tmp.unlink(missing_ok=True)
            if attempt < max_attempts:
                sleep(2.0 * attempt)
    raise PixabayError(f"Clip {candidate.id} download {max_attempts} koshish ke baad bhi fail: {last_error}")


def collect_clips(
    board: Storyboard,
    client: httpx.Client,
    api_key: str | None = None,
    cache_dir=None,
    max_scenes: int | None = None,
    sleep=time.sleep,
) -> list[SceneClip]:
    """Har scene ke liye ek alag clip (ek clip do scenes me dobara nahi lagta)."""
    used: set[int] = set()
    result: list[SceneClip] = []
    for scene in board.scenes[:max_scenes]:
        chosen, used_query = None, ""
        for q in query_options(scene.search_query, board.title):
            candidates = search_videos(q, client, api_key=api_key, cache_dir=cache_dir, sleep=sleep)
            chosen = pick_best(candidates, scene.duration, used)
            if chosen:
                used_query = q
                break
        if not chosen:
            raise PixabayError(f"Scene {scene.number} ke liye koi clip nahi mila ('{scene.search_query}')")
        path = download_clip(chosen, client, cache_dir=cache_dir, sleep=sleep)
        used.add(chosen.id)
        result.append(
            SceneClip(
                scene_number=scene.number,
                clip_id=chosen.id,
                path=str(path),
                query=used_query,
                width=chosen.width,
                height=chosen.height,
                duration=chosen.duration,
                portrait=chosen.is_portrait,
                page_url=chosen.page_url,
            )
        )
    return result
