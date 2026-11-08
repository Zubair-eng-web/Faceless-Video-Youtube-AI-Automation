import json

import httpx
import pytest

from dashboard.api_client import ApiClient, ApiError


def make_client(handler):
    return ApiClient("http://api.test", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_reads_channels_and_stats():
    def handler(request):
        if request.url.path == "/channels":
            return httpx.Response(200, json=[{"id": 1, "name": "C"}])
        if request.url.path == "/stats":
            return httpx.Response(200, json={"total": 3})
        return httpx.Response(404, json={"detail": "nahi"})

    client = make_client(handler)
    assert client.channels()[0]["name"] == "C"
    assert client.stats() == {"total": 3}


def test_error_detail_comes_from_api():
    client = make_client(lambda request: httpx.Response(409, json={"detail": "pehle se maujood"}))
    with pytest.raises(ApiError, match="pehle se maujood"):
        client.create_channel("C")


def test_validation_error_list_is_readable():
    detail = [{"msg": "too short", "loc": ["body", "name"]}]
    client = make_client(lambda request: httpx.Response(422, json={"detail": detail}))
    with pytest.raises(ApiError, match="too short"):
        client.create_channel("")


def test_connection_error_is_friendly():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ApiError, match="API server"):
        make_client(handler).health()


def test_generate_sends_only_filled_fields():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(202, json={"id": 1, "status": "queued"})

    make_client(handler).generate(topic="X", channel_id=2, niche="", language=None, seconds=30)
    assert seen["body"] == {"seconds": 30, "topic": "X", "channel_id": 2}


def test_videos_query_params():
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    make_client(handler).videos(status="ready", channel_id=2, limit=10)
    assert seen["params"] == {"limit": "10", "status": "ready", "channel_id": "2"}


def test_video_url_and_thumbnail_bytes():
    client = make_client(lambda request: httpx.Response(200, content=b"jpg"))
    assert client.video_url(5) == "http://api.test/videos/5/file"
    assert client.thumbnail_bytes(5) == b"jpg"
