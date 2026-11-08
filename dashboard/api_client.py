"""FastAPI backend se baat karne wala chhota client."""
import httpx


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", client=None, timeout: float = 20):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    @staticmethod
    def _detail(response) -> str:
        try:
            detail = response.json().get("detail")
        except Exception:
            detail = None
        if isinstance(detail, list):  # FastAPI ka 422 error list hota hai
            detail = "; ".join(str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in detail)
        return str(detail or f"HTTP {response.status_code}")

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self._client.request(method, self.base_url + path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(
                f"API server tak pohanch nahi saka ({self.base_url}). Kya server chal raha hai?"
            ) from exc
        if response.status_code >= 400:
            raise ApiError(self._detail(response))
        return response

    # ---------- Info ----------
    def health(self) -> dict:
        return self._request("GET", "/health").json()

    def gemini_status(self, force: bool = False) -> dict:
        params = {"force": "true"} if force else None
        return self._request("GET", "/settings/gemini", params=params).json()

    def set_gemini_key(self, key: str) -> dict:
        return self._request("POST", "/settings/gemini", json={"key": key}).json()

    def stats(self) -> dict:
        return self._request("GET", "/stats").json()

    # ---------- Channels ----------
    def channels(self) -> list[dict]:
        return self._request("GET", "/channels").json()

    def create_channel(self, name: str, niche: str = "", language: str = "English", voice=None) -> dict:
        body = {"name": name, "niche": niche, "language": language, "voice": voice}
        return self._request("POST", "/channels", json=body).json()

    def delete_channel(self, channel_id: int) -> dict:
        return self._request("DELETE", f"/channels/{channel_id}").json()

    def branding(self, channel_id: int) -> dict:
        return self._request("GET", f"/channels/{channel_id}/branding").json()

    def set_branding(self, channel_id: int, data: dict) -> dict:
        return self._request("PUT", f"/channels/{channel_id}/branding", json=data).json()

    # ---------- Videos ----------
    def videos(self, status=None, channel_id=None, limit: int = 50) -> list[dict]:
        params: dict = {"limit": limit}
        if status:
            params["status"] = status
        if channel_id is not None:
            params["channel_id"] = channel_id
        return self._request("GET", "/videos", params=params).json()

    def video(self, video_id: int) -> dict:
        return self._request("GET", f"/videos/{video_id}").json()

    def storyboard(self, video_id: int) -> dict:
        return self._request("GET", f"/videos/{video_id}/storyboard").json()

    def redo(self, video_id: int, edits=()) -> dict:
        return self._request("POST", f"/videos/{video_id}/redo", json={"edits": list(edits)}).json()

    def generate(self, topic=None, channel_id=None, niche=None, language=None, seconds: int = 40, voice=None) -> dict:
        body: dict = {"seconds": seconds}
        for key, value in (("topic", topic), ("channel_id", channel_id), ("niche", niche),
                           ("language", language), ("voice", voice)):
            if value not in (None, ""):
                body[key] = value
        return self._request("POST", "/generate", json=body).json()

    def approve(self, video_id: int) -> dict:
        return self._request("POST", f"/videos/{video_id}/approve").json()

    def reject(self, video_id: int) -> dict:
        return self._request("POST", f"/videos/{video_id}/reject").json()

    def video_url(self, video_id: int) -> str:
        return f"{self.base_url}/videos/{video_id}/file"

    def thumbnail_bytes(self, video_id: int) -> bytes:
        return self._request("GET", f"/videos/{video_id}/thumbnail").content

    # ---------- Publishing ----------
    def publish(self, video_id: int) -> dict:
        return self._request("POST", f"/videos/{video_id}/publish").json()

    def schedule(self, video_id: int, when: str) -> dict:
        return self._request("POST", f"/videos/{video_id}/schedule", json={"when": when}).json()

    def unschedule(self, video_id: int) -> dict:
        return self._request("POST", f"/videos/{video_id}/unschedule").json()

    def retry_publish(self, video_id: int) -> dict:
        return self._request("POST", f"/videos/{video_id}/retry-publish").json()

    def publishing_info(self) -> dict:
        return self._request("GET", "/publishing").json()

    def youtube_channels(self) -> list[dict]:
        return self._request("GET", "/youtube/channels").json()

    # ---------- Production aur analytics ----------
    def production(self) -> dict:
        return self._request("GET", "/production").json()

    def set_schedule(self, channel_id: int, daily_videos: int, produce_at: str, video_seconds: int = 40) -> dict:
        body = {"daily_videos": daily_videos, "produce_at": produce_at, "video_seconds": video_seconds}
        return self._request("PUT", f"/channels/{channel_id}/schedule", json=body).json()

    def refresh_analytics(self) -> dict:
        return self._request("POST", "/analytics/refresh", timeout=60).json()

    def analytics(self) -> dict:
        return self._request("GET", "/analytics").json()

    def insights(self) -> dict:
        return self._request("POST", "/analytics/insights", timeout=90).json()

    def create_variations(self, channel_id: int, topic: str, languages: list) -> dict:
        body = {"topic": topic, "languages": languages}
        return self._request("POST", f"/channels/{channel_id}/variations", json=body).json()
