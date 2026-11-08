import json
from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from app.core import db, db_production
from app.services.youtube import SCOPE_READONLY, SCOPE_UPLOAD, YouTubeError, YouTubeQuotaError, token_path
from app.services.youtube_stats import fetch_stats, refresh_stats, token_scopes


def http_error(status, reason=""):
    content = json.dumps({"error": {"errors": [{"reason": reason}], "message": reason}}).encode()
    return HttpError(Response({"status": str(status)}), content)


class FakeService:
    def __init__(self, stats=None, error=None):
        self.stats = stats or {}
        self.error = error
        self.calls = []

    def videos(self):
        return self

    def list(self, part, id):
        ids = id.split(",")
        self.calls.append(ids)

        def execute():
            if self.error:
                raise self.error
            return {"items": [{"id": i, "statistics": self.stats[i]} for i in ids if i in self.stats]}

        return SimpleNamespace(execute=execute)


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "app.db"
    db.init_db(p)
    return p


def setup_channel(path, tmp_path, name, scopes, youtube_ids):
    cid = db.create_channel(path, name)["id"]
    token_path(cid, tmp_path).write_text(json.dumps({"scopes": scopes}), encoding="utf-8")
    video_ids = []
    for yt_id in youtube_ids:
        video_id = db.create_job(path, cid, yt_id, "English")
        with db.connect(path) as con:
            con.execute("UPDATE videos SET status = 'published', youtube_id = ? WHERE id = ?", (yt_id, video_id))
        video_ids.append(video_id)
    return cid, video_ids


def test_token_scopes_reads_list_string_and_missing(tmp_path):
    token_path(1, tmp_path).write_text(json.dumps({"scopes": ["a", "b"]}))
    token_path(2, tmp_path).write_text(json.dumps({"scopes": "a b"}))
    assert token_scopes(1, tmp_path) == {"a", "b"}
    assert token_scopes(2, tmp_path) == {"a", "b"}
    assert token_scopes(3, tmp_path) == set()


def test_fetch_stats_parses_counts_and_dedupes():
    service = FakeService({"a": {"viewCount": "12", "likeCount": "3", "commentCount": "1"},
                           "b": {"viewCount": "5"}})
    result = fetch_stats(service, ["a", "b", "a"])
    assert result == {"a": {"views": 12, "likes": 3, "comments": 1},
                      "b": {"views": 5, "likes": 0, "comments": 0}}
    assert service.calls == [["a", "b"]]


def test_fetch_stats_batches_ids():
    service = FakeService()
    fetch_stats(service, [f"id{i}" for i in range(110)])
    assert [len(c) for c in service.calls] == [50, 50, 10]


def test_fetch_stats_maps_quota_error():
    with pytest.raises(YouTubeQuotaError):
        fetch_stats(FakeService(error=http_error(403, "quotaExceeded")), ["a"])


def test_refresh_updates_videos_with_readonly_scope(path, tmp_path):
    cid, video_ids = setup_channel(path, tmp_path, "C", [SCOPE_UPLOAD, SCOPE_READONLY], ["a", "b"])
    service = FakeService({"a": {"viewCount": "10", "likeCount": "2", "commentCount": "1"},
                           "b": {"viewCount": "20"}})
    summary = refresh_stats(path, service_factory=lambda channel_id: service, tokens_dir=tmp_path)
    assert summary == {"updated": 2, "needs_reconnect": [], "errors": []}
    assert db.get_video(path, video_ids[0])["views"] == 10
    assert db.get_video(path, video_ids[1])["views"] == 20


def test_refresh_flags_channels_that_need_reconnect(path, tmp_path):
    cid, _ = setup_channel(path, tmp_path, "C", [SCOPE_UPLOAD], ["a"])

    def factory(channel_id):
        raise AssertionError("service nahi banni chahiye")

    summary = refresh_stats(path, service_factory=factory, tokens_dir=tmp_path)
    assert summary["needs_reconnect"] == [cid]
    assert summary["updated"] == 0


def test_refresh_records_errors_and_continues(path, tmp_path):
    bad, _ = setup_channel(path, tmp_path, "Bad", [SCOPE_READONLY], ["a"])
    good, good_videos = setup_channel(path, tmp_path, "Good", [SCOPE_READONLY], ["b"])

    def factory(channel_id):
        if channel_id == bad:
            raise YouTubeError("login expire")
        return FakeService({"b": {"viewCount": "7"}})

    summary = refresh_stats(path, service_factory=factory, tokens_dir=tmp_path)
    assert summary["updated"] == 1
    assert "login expire" in summary["errors"][0]
    assert db.get_video(path, good_videos[0])["views"] == 7


def test_refresh_skips_videos_missing_from_response(path, tmp_path):
    cid, video_ids = setup_channel(path, tmp_path, "C", [SCOPE_READONLY], ["a", "gone"])
    summary = refresh_stats(path, service_factory=lambda c: FakeService({"a": {"viewCount": "3"}}), tokens_dir=tmp_path)
    assert summary["updated"] == 1
    assert db.get_video(path, video_ids[1])["views"] is None
