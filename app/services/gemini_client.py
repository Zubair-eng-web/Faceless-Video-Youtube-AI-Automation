"""Gemini ka chhota wrapper: JSON jawab, pydantic validation, retry, rate-limit throttle."""
import time
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

FENCE = "`" * 3
# Ye errors dobara try karne se theek nahi hote (galat key, galat model, galat request)
NO_RETRY_CODES = {400, 401, 403, 404}


class GeminiError(RuntimeError):
    pass


def _clean_json(text) -> str:
    text = (text or "").strip()
    if text.startswith(FENCE):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


class GeminiClient:
    def __init__(self, api_key=None, model=None, client=None, max_attempts=None, base_delay=None,
                 sleep=time.sleep, min_interval=None, clock=time.monotonic):
        self.model = model or settings.gemini_model
        self.max_attempts = max_attempts if max_attempts is not None else settings.gemini_max_attempts
        self.base_delay = base_delay if base_delay is not None else settings.gemini_retry_delay
        self.min_interval = min_interval if min_interval is not None else settings.gemini_min_interval_seconds
        self._sleep = sleep
        self._clock = clock
        self._last_call = None
        self.requests_made = 0  # kitni requests gayin (API usage record karne ke liye)
        if client is None:
            key = api_key or settings.gemini_api_key
            if not key:
                raise GeminiError("GEMINI_API_KEY .env me nahi mili")
            client = genai.Client(api_key=key)
        self._client = client

    def _throttle(self) -> None:
        """Free tier ki per-minute limit ke liye: do requests ke beech kam az kam min_interval second."""
        if self.min_interval > 0 and self._last_call is not None:
            wait = self.min_interval - (self._clock() - self._last_call)
            if wait > 0:
                self._sleep(wait)
        self._last_call = self._clock()

    def generate_json(self, prompt: str, schema: type[T], system: str | None = None, temperature: float = 0.9) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self._throttle()
                self.requests_made += 1
                response = self._client.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
                return schema.model_validate_json(_clean_json(response.text))
            except Exception as exc:
                last_error = exc
                code = getattr(exc, "code", None)
                if code in NO_RETRY_CODES:
                    raise GeminiError(f"Gemini ne request reject ki ({code}): {exc}") from exc
                if attempt < self.max_attempts:
                    self._sleep(self.base_delay * attempt)
        raise GeminiError(f"Gemini {self.max_attempts} koshish ke baad bhi fail: {last_error}") from last_error


def make_gemini_client(model: str | None = None) -> GeminiClient:
    """Provider settings (AI_PROVIDER) ke mutabiq client banata hai. Naya provider yahin jor sakte hain."""
    provider = (settings.ai_provider or "gemini").strip().lower()
    if provider == "gemini":
        return GeminiClient(model=model) if model else GeminiClient()
    raise GeminiError(f"AI_PROVIDER '{provider}' abhi supported nahi (supported: gemini)")