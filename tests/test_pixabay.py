import time

import httpx
import pytest

from app.core.config import settings
from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard
from app.services.pixabay import (
    ClipCandidate,
    PixabayError,
    collect_clips,
    download_clip,
    parse_hit,
    pick_best,
    query_options,
    search_videos,
)


def variant(w, h, url=True):
    return {"url": f"https://cdn.test/{w}x{h}.mp4" if url else "", "width": w, "height": h}


def hit(id_, large, medium=None, small=None, duration=10, large_url=True):
    videos = {"large": variant(*large, url=large_url)}
    if medium:
        videos["medium"] = variant(*medium)
    if small:
        videos["small"] = variant(*small)
    return {"id": id_, "pageURL": f"https://pixabay.com/videos/{id_}/", "tags": "a, b",
            "duration": duration, "videos": videos}


def cand(id_, w=1920, h=1080, duration=10):
    return ClipCandidate(id=id_, page_url="", tags="", duration=duration,
                         url="https://cdn.test/x.mp4", width=w, height=h)


def make_client(payloads, counter):
    """payloads: query -> hits ki list. Pixabay API aur download dono fake."""
    def handler(request):
        if request.url.host == "pixabay.com":
            counter["api"] = counter.get("api", 0) + 1
            return httpx.Response(200, json={"hits": payloads.get(request.url.params.get("q"), [])})
        counter["dl"] = counter.get("dl", 0) + 1
        return httpx.Response(200, content=b"video-bytes")
    return httpx.Client(transport=httpx.MockTransport(handler))


def make_board(*queries):
    scenes = [SceneDraft(narration="one two three four five six", visual_description="v", search_query=q)
              for q in queries]
    return build_storyboard(ScriptDraft(title="Space Facts", hook="h", scenes=scenes))


# ---------- parse_hit ----------
def test_parse_hit_skips_4k_when_1080_exists():
    c = parse_hit(hit(1, large=(3840, 2160), medium=(1920, 1080), small=(1280, 720)))
    assert (c.width, c.height) == (1920, 1080)


def test_parse_hit_portrait_clip():
    c = parse_hit(hit(2, large=(1080, 1920), medium=(720, 1280)))
    assert (c.width, c.height) == (1080, 1920)
    assert c.is_portrait is True


def test_parse_hit_uses_largest_when_none_is_big_enough():
    c = parse_hit(hit(3, large=(1280, 720), medium=(640, 360)))
    assert (c.width, c.height) == (1280, 720)


def test_parse_hit_skips_empty_url():
    c = parse_hit(hit(4, large=(1920, 1080), medium=(1280, 720), large_url=False))
    assert (c.width, c.height) == (1280, 720)


def test_parse_hit_returns_none_without_usable_video():
    assert parse_hit(hit(5, large=(1920, 1080), large_url=False)) is None
    assert parse_hit({}) is None


# ---------- pick_best ----------
def test_pick_best_prefers_portrait():
    assert pick_best([cand(1), cand(2, 1080, 1920)], 5).id == 2


def test_pick_best_prefers_long_enough_clip():
    assert pick_best([cand(1, duration=3), cand(2, duration=12)], 8).id == 2


def test_pick_best_skips_used_clips():
    assert pick_best([cand(1), cand(2)], 5, used={1}).id == 2


def test_pick_best_returns_none_when_nothing_left():
    assert pick_best([cand(1)], 5, used={1}) is None
    assert pick_best([], 5) is None


# ---------- search_videos ----------
def test_search_parses_hits_and_sends_params(tmp_path):
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"hits": [hit(1, (1080, 1920), (720, 1280))]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = search_videos("space walk", client, api_key="k", cache_dir=tmp_path)
    assert [c.id for c in result] == [1]
    assert seen["key"] == "k"
    assert seen["q"] == "space walk"
    assert seen["safesearch"] == "true"


def test_search_uses_cache_for_same_query(tmp_path):
    counter = {}
    client = make_client({"space": [hit(1, (1920, 1080))]}, counter)
    search_videos("space", client, api_key="k", cache_dir=tmp_path)
    again = search_videos("space", client, api_key="k", cache_dir=tmp_path)
    assert counter["api"] == 1
    assert again[0].id == 1


def test_search_cache_expires_after_24_hours(tmp_path):
    counter = {}
    client = make_client({"space": [hit(1, (1920, 1080))]}, counter)
    search_videos("space", client, api_key="k", cache_dir=tmp_path)
    search_videos("space", client, api_key="k", cache_dir=tmp_path, now=lambda: time.time() + 25 * 3600)
    assert counter["api"] == 2


def test_search_does_not_retry_bad_key(tmp_path):
    state = {"n": 0}
    sleeps = []

    def handler(request):
        state["n"] += 1
        return httpx.Response(400, text="[ERROR 400] Invalid API key")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(PixabayError):
        search_videos("space", client, api_key="bad", cache_dir=tmp_path, sleep=sleeps.append)
    assert state["n"] == 1
    assert sleeps == []


def test_search_retries_after_rate_limit(tmp_path):
    state = {"n": 0}
    sleeps = []

    def handler(request):
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, text="Too many requests")
        return httpx.Response(200, json={"hits": [hit(1, (1920, 1080))]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = search_videos("space", client, api_key="k", cache_dir=tmp_path, sleep=sleeps.append)
    assert len(result) == 1
    assert sleeps == [5.0]


def test_search_without_key_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "pixabay_api_key", "")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(PixabayError):
        search_videos("space", client, api_key=None, cache_dir=tmp_path)


# ---------- download ----------
def test_download_writes_file_and_reuses_cache(tmp_path):
    counter = {}
    client = make_client({}, counter)
    c = cand(7)
    first = download_clip(c, client, cache_dir=tmp_path)
    second = download_clip(c, client, cache_dir=tmp_path)
    assert first == second
    assert first.name == "pixabay_7.mp4"
    assert first.read_bytes() == b"video-bytes"
    assert counter["dl"] == 1


# ---------- collect_clips ----------
def test_collect_clips_never_reuses_a_clip(tmp_path):
    two = [hit(1, (1080, 1920), (720, 1280)), hit(2, (1080, 1920), (720, 1280))]
    client = make_client({"stars": two}, {})
    clips = collect_clips(make_board("stars", "stars"), client, api_key="k", cache_dir=tmp_path)
    assert [c.clip_id for c in clips] == [1, 2]
    assert all(c.portrait for c in clips)


def test_collect_clips_falls_back_to_shorter_query(tmp_path):
    payloads = {"slow motion ocean waves": [], "slow motion": [hit(3, (1920, 1080))]}
    client = make_client(payloads, {})
    clips = collect_clips(make_board("slow motion ocean waves"), client, api_key="k", cache_dir=tmp_path)
    assert clips[0].query == "slow motion"
    assert clips[0].clip_id == 3
    assert clips[0].portrait is False


def test_collect_clips_raises_when_nothing_found(tmp_path):
    client = make_client({}, {})
    with pytest.raises(PixabayError):
        collect_clips(make_board("nothing here"), client, api_key="k", cache_dir=tmp_path)


def test_query_options_dedupes_and_orders():
    assert query_options("a b c", "Title") == ["a b c", "a b", "Title"]
    assert query_options("a", "a") == ["a"]
    assert query_options("a b", "T") == ["a b", "T"]
