import json
from types import SimpleNamespace

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response

from app.services.youtube import (
    YouTubeAuthError,
    YouTubeError,
    YouTubeQuotaError,
    authorize,
    build_body,
    clean_description,
    clean_title,
    is_connected,
    load_credentials,
    set_thumbnail,
    token_path,
    upload_to_youtube,
    upload_video,
)


def http_error(status, reason=""):
    content = json.dumps({"error": {"errors": [{"reason": reason}], "message": reason}}).encode()
    return HttpError(Response({"status": str(status)}), content)


def fake_media(path, **kwargs):
    return ("media", path)


class FakeFlow:
    def __init__(self, secret, scopes):
        self.secret = secret
        self.scopes = scopes

    def run_local_server(self, **kwargs):
        return SimpleNamespace(to_json=lambda: json.dumps({"refresh_token": "r", "valid": True}))


class FakeCreds:
    def __init__(self, valid, refresh_token, fail):
        self.valid = valid
        self.refresh_token = refresh_token
        self.fail = fail
        self.refreshed = False

    @classmethod
    def from_authorized_user_file(cls, path, scopes):
        data = json.load(open(path, encoding="utf-8"))
        return cls(data["valid"], data.get("refresh_token"), data.get("fail", False))

    def refresh(self, request):
        if self.fail:
            raise RefreshError("expired")
        self.valid = True
        self.refreshed = True

    def to_json(self):
        return json.dumps({"valid": self.valid, "refresh_token": self.refresh_token, "refreshed": self.refreshed})


class FakeRequest:
    def __init__(self, steps):
        self.steps = list(steps)

    def next_chunk(self):
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeVideos:
    def __init__(self, request):
        self.request = request
        self.kwargs = None

    def insert(self, **kwargs):
        self.kwargs = kwargs
        return self.request


def fake_service(steps):
    videos = FakeVideos(FakeRequest(steps))
    return SimpleNamespace(videos=lambda: videos), videos


def make_video(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"video")
    return video


# ---------- Login ----------
def test_token_path_and_is_connected(tmp_path):
    assert token_path(3, tmp_path).name == "youtube_3.json"
    assert is_connected(3, tmp_path) is False
    token_path(3, tmp_path).write_text("{}")
    assert is_connected(3, tmp_path) is True


def test_authorize_saves_token(tmp_path):
    secret = tmp_path / "client_secret.json"
    secret.write_text("{}")
    path = authorize(2, client_secret=secret, tokens_dir=tmp_path / "tokens", flow_factory=FakeFlow)
    assert path == tmp_path / "tokens" / "youtube_2.json"
    assert json.loads(path.read_text())["refresh_token"] == "r"


def test_authorize_without_client_secret(tmp_path):
    with pytest.raises(YouTubeAuthError):
        authorize(1, client_secret=tmp_path / "nope.json", tokens_dir=tmp_path, flow_factory=FakeFlow)


def test_load_credentials_requires_token(tmp_path):
    with pytest.raises(YouTubeAuthError, match="connect"):
        load_credentials(1, tokens_dir=tmp_path, credentials_cls=FakeCreds)


def test_load_credentials_refreshes_and_saves(tmp_path):
    token_path(1, tmp_path).write_text(json.dumps({"valid": False, "refresh_token": "r"}))
    creds = load_credentials(1, tokens_dir=tmp_path, credentials_cls=FakeCreds, request_factory=lambda: None)
    assert creds.valid is True
    assert json.loads(token_path(1, tmp_path).read_text())["refreshed"] is True


def test_load_credentials_refresh_failure(tmp_path):
    token_path(1, tmp_path).write_text(json.dumps({"valid": False, "refresh_token": "r", "fail": True}))
    with pytest.raises(YouTubeAuthError, match="expire"):
        load_credentials(1, tokens_dir=tmp_path, credentials_cls=FakeCreds, request_factory=lambda: None)


# ---------- Body ----------
def test_clean_title_strips_symbols_and_truncates():
    assert clean_title("  A <b>  title ") == "A b title"
    assert len(clean_title("x" * 300)) == 100


def test_clean_title_rejects_empty():
    with pytest.raises(ValueError):
        clean_title(" <> ")


def test_clean_description_respects_byte_limit():
    assert clean_description("a<b>c") == "a b c"
    assert len(clean_description("\u00e9" * 4000).encode("utf-8")) <= 5000


def test_build_body_defaults():
    body = build_body("Title", "Desc", ["a", " "], "private", None)
    assert body["snippet"]["categoryId"] == "22"
    assert body["snippet"]["tags"] == ["a"]
    assert body["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": False}
    assert "tags" not in build_body("T", "D", [], "private", None)["snippet"]


def test_build_body_schedule_requires_private():
    with pytest.raises(ValueError):
        build_body("T", "D", [], "public", "2026-11-07T10:00:00Z")
    body = build_body("T", "D", [], "private", "2026-11-07T10:00:00Z")
    assert body["status"]["publishAt"] == "2026-11-07T10:00:00Z"


def test_build_body_rejects_bad_privacy():
    with pytest.raises(ValueError):
        build_body("T", "D", [], "secret", None)


# ---------- Upload ----------
def test_upload_video_returns_id_and_reports_progress(tmp_path):
    service, videos = fake_service([(SimpleNamespace(progress=lambda: 0.5), None), (None, {"id": "abc"})])
    seen = []
    video_id = upload_video(service, make_video(tmp_path), "T", "D", media_cls=fake_media, progress=seen.append)
    assert video_id == "abc"
    assert seen == [0.5]
    assert videos.kwargs["part"] == "snippet,status"
    assert videos.kwargs["body"]["snippet"]["title"] == "T"
    assert videos.kwargs["body"]["status"]["privacyStatus"] == "private"


def test_upload_video_retries_server_errors(tmp_path):
    service, _ = fake_service([http_error(503), (None, {"id": "abc"})])
    sleeps = []
    assert upload_video(service, make_video(tmp_path), "T", "D", media_cls=fake_media, sleep=sleeps.append) == "abc"
    assert sleeps == [2]


def test_upload_video_maps_quota_error(tmp_path):
    service, _ = fake_service([http_error(403, "quotaExceeded")])
    with pytest.raises(YouTubeQuotaError):
        upload_video(service, make_video(tmp_path), "T", "D", media_cls=fake_media, sleep=lambda s: None)


def test_upload_video_does_not_retry_client_errors(tmp_path):
    service, videos = fake_service([http_error(400, "badRequest"), (None, {"id": "x"})])
    sleeps = []
    with pytest.raises(YouTubeError):
        upload_video(service, make_video(tmp_path), "T", "D", media_cls=fake_media, sleep=sleeps.append)
    assert len(videos.request.steps) == 1
    assert sleeps == []


def test_upload_video_missing_file(tmp_path):
    with pytest.raises(YouTubeError):
        upload_video(object(), tmp_path / "nope.mp4", "T", "D", media_cls=fake_media)


def test_set_thumbnail_calls_api(tmp_path):
    seen = {}

    class Thumbs:
        def set(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(execute=lambda: {})

    service = SimpleNamespace(thumbnails=lambda: Thumbs())
    image = tmp_path / "t.jpg"
    image.write_bytes(b"jpg")
    set_thumbnail(service, "abc", image, media_cls=fake_media)
    assert seen["videoId"] == "abc"


# ---------- upload_to_youtube ----------
def test_upload_to_youtube_success(tmp_path):
    calls = {}

    def upload_fn(service, path, title, description, **kwargs):
        calls["kwargs"] = kwargs
        return "vid1"

    result = upload_to_youtube(
        1, "v.mp4", "T", "D", tags=["a"], thumbnail_path="t.jpg", privacy="private",
        load_fn=lambda cid, d: "creds", build_fn=lambda c: "svc", upload_fn=upload_fn,
        thumb_fn=lambda s, v, p: calls.setdefault("thumb", (v, p)),
    )
    assert result == {"video_id": "vid1", "thumbnail_error": None}
    assert calls["thumb"] == ("vid1", "t.jpg")
    assert calls["kwargs"]["privacy"] == "private"


def test_upload_to_youtube_thumbnail_failure_is_not_fatal():
    def bad_thumb(service, video_id, path):
        raise YouTubeError("channel verify nahi")

    result = upload_to_youtube(
        1, "v.mp4", "T", "D", thumbnail_path="t.jpg",
        load_fn=lambda cid, d: "creds", build_fn=lambda c: "svc",
        upload_fn=lambda *a, **k: "vid1", thumb_fn=bad_thumb,
    )
    assert result["video_id"] == "vid1"
    assert "channel verify" in result["thumbnail_error"]
