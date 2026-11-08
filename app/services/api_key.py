"""Gemini API key ka manager: halat ki jaanch, nayi key ki testing, .env mein save aur turant apply."""
import os
import re
import time
from pathlib import Path

from pydantic import BaseModel

from app.core.config import BASE_DIR, settings

ENV_NAME = "GEMINI_API_KEY"
OK_CACHE_SECONDS = 600
BAD_CACHE_SECONDS = 120
_cache = {"at": 0.0, "data": None, "ttl": 0}


class KeyBody(BaseModel):
    key: str


class _Ping(BaseModel):
    ok: bool = True


def clean_key(raw) -> str:
    k = (raw or "").strip().strip('"').strip("'").strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{20,}", k):
        raise ValueError("Key ghalat lagti hai (bohat chhoti hai, ya space ya ajeeb huroof hain). "
                         "Poori key dobara copy karein.")
    return k


def mask(key) -> str:
    key = key or ""
    return f"{key[:4]}...{key[-4:]}" if len(key) >= 12 else ("*" * len(key))


def field_name() -> str | None:
    for name in type(settings).model_fields:
        if "gemini" in name.lower() and "key" in name.lower():
            return name
    return None


def current_key() -> str:
    name = field_name()
    val = getattr(settings, name, None) if name else None
    if hasattr(val, "get_secret_value"):
        val = val.get_secret_value()
    return (val or os.environ.get(ENV_NAME) or "").strip()


def classify(exc) -> dict:
    low = str(exc).lower()
    if any(w in low for w in ("429", "quota", "resource_exhausted", "rate limit", "rate-limit")):
        return {"state": "limited",
                "message": "Free quota ya rate limit khatam hai. Thori der baad theek ho jata hai, key badalne ki zaroorat nahi."}
    if any(w in low for w in ("api key", "api_key", "expired", "permission", "unauthenticated",
                              "401", "403", "gemini_api_key")):
        return {"state": "invalid", "message": "Key expire ho gayi hai ya galat hai."}
    return {"state": "error", "message": f"Key ki jaanch nahi ho saki: {str(exc)[:160]}"}


def check_key(key, client_cls=None) -> dict:
    """Ek chhoti asli call (sirf 1 koshish) se key parakhna."""
    try:
        if client_cls is None:
            from app.services.gemini_client import GeminiClient as client_cls
        client_cls(api_key=key, max_attempts=1).generate_json("Reply with ok=true.", _Ping, temperature=0)
        return {"state": "ok", "message": "Key theek kaam kar rahi hai."}
    except Exception as exc:  # noqa: BLE001
        return classify(exc)


def save_env(env_path, key: str) -> None:
    p = Path(env_path)
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    out, done = [], False
    for line in lines:
        if re.match(rf"^\s*(export\s+)?{ENV_NAME}\s*=", line):
            if not done:
                out.append(f"{ENV_NAME}={key}")
                done = True
            continue
        out.append(line)
    if not done:
        out.append(f"{ENV_NAME}={key}")
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    tmp.replace(p)


def apply_key(key: str) -> None:
    os.environ[ENV_NAME] = key
    name = field_name()
    if name:
        old = getattr(settings, name, None)
        new = key
        if hasattr(old, "get_secret_value"):
            from pydantic import SecretStr
            new = SecretStr(key)
        try:
            setattr(settings, name, new)
        except Exception:  # noqa: BLE001 - environment variable phir bhi lag chuka
            pass


def _remember(data: dict) -> dict:
    _cache.update(at=time.time(), data=data,
                  ttl=OK_CACHE_SECONDS if data["state"] == "ok" else BAD_CACHE_SECONDS)
    return data


def get_status(force: bool = False) -> dict:
    key = current_key()
    if not key:
        return {"state": "missing", "message": "Gemini API key set nahi hai.", "masked": ""}
    fresh = _cache["data"] is not None and time.time() - _cache["at"] < _cache["ttl"]
    if fresh and not force and _cache["data"].get("masked") == mask(key):
        return _cache["data"]
    return _remember({**check_key(key), "masked": mask(key)})


def set_key(raw, env_path=None, checker=None) -> dict:
    key = clean_key(raw)
    result = (checker or check_key)(key)
    if result["state"] == "invalid":
        raise ValueError("Ye key kaam nahi kar rahi (expire ya galat). Naye key se dobara koshish karein. "
                         "Purani key waisi hi rahi.")
    save_env(env_path or (BASE_DIR / ".env"), key)
    apply_key(key)
    _remember({**result, "masked": mask(key)})
    msg = {"ok": "Nayi key save ho gayi aur kaam kar rahi hai.",
           "limited": "Key save ho gayi (abhi free quota khatam hai, baad mein chalegi).",
           }.get(result["state"], "Key save ho gayi, lekin abhi jaanch nahi ho saki.")
    return {"state": result["state"], "message": msg, "masked": mask(key)}
