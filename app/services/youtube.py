"""YouTube: OAuth login (har channel ka alag token) aur video upload."""
import time
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from app.core.config import BASE_DIR

SCOPE_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
SCOPE_READONLY = "https://www.googleapis.com/auth/youtube.readonly"
SCOPES = [SCOPE_UPLOAD, SCOPE_READONLY]
DEFAULT_CLIENT_SECRET = BASE_DIR / "client_secret.json"
DEFAULT_TOKENS_DIR = BASE_DIR / "data" / "tokens"
TITLE_MAX = 100
DESCRIPTION_MAX_BYTES = 5000
PRIVACY = ("private", "unlisted", "public")
RETRY_STATUS = {500, 502, 503, 504}
CHUNK_SIZE = 8 * 1024 * 1024  # 256 KB ka multiple hona zaroori hai


class YouTubeError(RuntimeError):
    pass


class YouTubeAuthError(YouTubeError):
    pass


class YouTubeQuotaError(YouTubeError):
    pass


# ---------- Login ----------
def token_path(channel_id, tokens_dir=None) -> Path:
    return Path(tokens_dir or DEFAULT_TOKENS_DIR) / f"youtube_{channel_id}.json"


def is_connected(channel_id, tokens_dir=None) -> bool:
    return token_path(channel_id, tokens_dir).exists()


def authorize(channel_id, client_secret=None, tokens_dir=None,
              flow_factory=InstalledAppFlow.from_client_secrets_file) -> Path:
    """Browser khol kar login karwata hai aur token save karta hai."""
    secret = Path(client_secret or DEFAULT_CLIENT_SECRET)
    if not secret.exists():
        raise YouTubeAuthError(f"client_secret.json nahi mili: {secret}")
    flow = flow_factory(str(secret), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    path = token_path(channel_id, tokens_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json(), encoding="utf-8")
    return path


def load_credentials(channel_id, tokens_dir=None, credentials_cls=Credentials, request_factory=Request):
    path = token_path(channel_id, tokens_dir)
    if not path.exists():
        raise YouTubeAuthError(
            f"Channel {channel_id} YouTube se connect nahi hai. "
            f"Chalayen: python -m scripts.connect_youtube {channel_id}"
        )
    creds = credentials_cls.from_authorized_user_file(str(path), None)  # token me jo scopes hain wahi use hon
    if not creds.valid:
        if not creds.refresh_token:
            raise YouTubeAuthError(f"Token mein refresh token nahi. Dobara connect karein (channel {channel_id}).")
        try:
            creds.refresh(request_factory())
        except RefreshError as exc:
            raise YouTubeAuthError(
                f"Login expire ho gaya. Dobara connect karein: python -m scripts.connect_youtube {channel_id}"
            ) from exc
        path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_service(creds):
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


# ---------- Upload ----------
def clean_title(title: str) -> str:
    title = " ".join(title.replace("<", " ").replace(">", " ").split())[:TITLE_MAX].rstrip()
    if not title:
        raise ValueError("Title khali hai")
    return title


def clean_description(text: str) -> str:
    text = text.replace("<", " ").replace(">", " ").strip()
    return text.encode("utf-8")[:DESCRIPTION_MAX_BYTES].decode("utf-8", "ignore")


def build_body(title, description, tags, privacy, publish_at, category_id="22", made_for_kids=False) -> dict:
    if privacy not in PRIVACY:
        raise ValueError(f"privacy in me se ho: {', '.join(PRIVACY)}")
    if publish_at and privacy != "private":
        raise ValueError("Scheduled publish ke liye privacy 'private' honi chahiye")
    snippet = {
        "title": clean_title(title),
        "description": clean_description(description),
        "categoryId": category_id,
    }
    tag_list = [t.replace("<", " ").replace(">", " ").strip() for t in tags if t.strip()]
    if tag_list:
        snippet["tags"] = tag_list
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": made_for_kids}
    if publish_at:
        status["publishAt"] = publish_at
    return {"snippet": snippet, "status": status}


def _translate(exc: HttpError) -> YouTubeError:
    status = int(exc.resp.status)
    content = exc.content.decode("utf-8", "replace") if isinstance(exc.content, bytes) else str(exc.content)
    if "quotaExceeded" in content or "uploadLimitExceeded" in content:
        return YouTubeQuotaError(f"YouTube ki roz ki limit khatam ({status}): {content[:200]}")
    if status == 401 or "invalid_grant" in content:
        return YouTubeAuthError(f"YouTube login masla ({status}): {content[:200]}")
    return YouTubeError(f"YouTube error {status}: {content[:300]}")


def upload_video(service, video_path, title, description, tags=(), privacy="private", publish_at=None,
                 category_id="22", made_for_kids=False, media_cls=MediaFileUpload,
                 sleep=time.sleep, max_retries=5, progress=None) -> str:
    path = Path(video_path)
    if not path.exists():
        raise YouTubeError(f"Video file nahi mili: {path}")
    body = build_body(title, description, tags, privacy, publish_at, category_id, made_for_kids)
    media = media_cls(str(path), mimetype="video/mp4", chunksize=CHUNK_SIZE, resumable=True)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    retries = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status is not None and progress:
                progress(status.progress())
        except HttpError as exc:
            if int(exc.resp.status) in RETRY_STATUS and retries < max_retries:
                retries += 1
                sleep(2 ** retries)
                continue
            raise _translate(exc) from exc
        except OSError as exc:  # network toota
            if retries < max_retries:
                retries += 1
                sleep(2 ** retries)
                continue
            raise YouTubeError(f"Network masla: {exc}") from exc
    video_id = response.get("id")
    if not video_id:
        raise YouTubeError(f"YouTube ne video id nahi di: {response}")
    return video_id


def set_thumbnail(service, video_id: str, thumbnail_path, media_cls=MediaFileUpload) -> None:
    media = media_cls(str(thumbnail_path), mimetype="image/jpeg")
    try:
        service.thumbnails().set(videoId=video_id, media_body=media).execute()
    except HttpError as exc:
        raise _translate(exc) from exc


def upload_to_youtube(channel_id, video_path, title, description, tags=(), thumbnail_path=None,
                      privacy="private", publish_at=None, tokens_dir=None, progress=None,
                      load_fn=load_credentials, build_fn=build_service,
                      upload_fn=upload_video, thumb_fn=set_thumbnail) -> dict:
    """Login, upload aur thumbnail. Thumbnail fail ho to upload fail nahi hota."""
    creds = load_fn(channel_id, tokens_dir)
    service = build_fn(creds)
    video_id = upload_fn(service, video_path, title, description, tags=tags, privacy=privacy,
                         publish_at=publish_at, progress=progress)
    result = {"video_id": video_id, "thumbnail_error": None}
    if thumbnail_path:
        try:
            thumb_fn(service, video_id, thumbnail_path)
        except YouTubeError as exc:
            result["thumbnail_error"] = str(exc)
    return result
