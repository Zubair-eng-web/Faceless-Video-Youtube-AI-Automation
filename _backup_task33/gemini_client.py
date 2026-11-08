"""Gemini ka chhota wrapper: JSON jawab, pydantic validation, retry."""
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
    def __init__(self, api_key=None, model=None, client=None, max_attempts=4, base_delay=5.0, sleep=time.sleep):
        self.model = model or settings.gemini_model
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self._sleep = sleep
        if client is None:
            key = api_key or settings.gemini_api_key
            if not key:
                raise GeminiError("GEMINI_API_KEY .env me nahi mili")
            client = genai.Client(api_key=key)
        self._client = client

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
