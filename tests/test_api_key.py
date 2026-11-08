import os
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.config import settings
from app.services import api_key as ak
from dashboard.api_client import ApiClient


def test_clean_key_and_mask():
    assert ak.clean_key('  "AIzaSyABCDEFGHIJKLMNOPQRST"  ') == "AIzaSyABCDEFGHIJKLMNOPQRST"
    for bad in ("", "short", "has space inside the key value 123456"):
        with pytest.raises(ValueError):
            ak.clean_key(bad)
    assert ak.mask("AIzaSyABCDEFGHIJKLMNOPQRST") == "AIza...QRST" and "ABCDEFGH" not in ak.mask("AIzaSyABCDEFGHIJKLMNOPQRST")


def test_save_env_replaces_and_appends(tmp_path):
    p = tmp_path / ".env"
    p.write_text("A=1\nGEMINI_API_KEY=old\nB=2\nGEMINI_API_KEY=dup\n", encoding="utf-8")
    ak.save_env(p, "NEW")
    assert p.read_text(encoding="utf-8") == "A=1\nGEMINI_API_KEY=NEW\nB=2\n"
    q = tmp_path / "new.env"
    ak.save_env(q, "K")
    assert q.read_text(encoding="utf-8") == "GEMINI_API_KEY=K\n"


def test_classify():
    assert ak.classify(RuntimeError("400 API key expired. Please renew"))["state"] == "invalid"
    assert ak.classify(RuntimeError("429 RESOURCE_EXHAUSTED quota"))["state"] == "limited"
    assert ak.classify(RuntimeError("timeout"))["state"] == "error"
    assert ak.classify(RuntimeError("INVALID_ARGUMENT bad model"))["state"] == "error"


def test_check_key_with_fake_clients():
    class Good:
        def __init__(self, api_key=None, max_attempts=4):
            assert max_attempts == 1

        def generate_json(self, prompt, schema, system=None, temperature=0.9):
            return schema()

    class Bad(Good):
        def generate_json(self, *a, **k):
            raise RuntimeError("API key not valid")

    assert ak.check_key("k", Good)["state"] == "ok"
    assert ak.check_key("k", Bad)["state"] == "invalid"


def _stub_settings(monkeypatch):
    name = ak.field_name()
    assert name, "settings mein gemini key ka field nahi mila"
    monkeypatch.setattr(settings, name, "oldkey")
    monkeypatch.setenv("GEMINI_API_KEY", "oldkey")
    return name


def test_set_key_rejects_invalid_and_keeps_old(tmp_path, monkeypatch):
    _stub_settings(monkeypatch)
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=oldkey\n", encoding="utf-8")
    with pytest.raises(ValueError):
        ak.set_key("AIzaSyABCDEFGHIJKLMNOPQRST", env, checker=lambda k: {"state": "invalid", "message": "x"})
    assert env.read_text(encoding="utf-8") == "GEMINI_API_KEY=oldkey\n" and ak.current_key() == "oldkey"


def test_set_key_saves_and_applies(tmp_path, monkeypatch):
    _stub_settings(monkeypatch)
    env = tmp_path / ".env"
    res = ak.set_key("AIzaSyABCDEFGHIJKLMNOPQRST", env, checker=lambda k: {"state": "ok", "message": "ok"})
    assert res["state"] == "ok" and "ABCDEFGH" not in str(res)
    assert env.read_text(encoding="utf-8") == "GEMINI_API_KEY=AIzaSyABCDEFGHIJKLMNOPQRST\n"
    assert ak.current_key() == "AIzaSyABCDEFGHIJKLMNOPQRST" and os.environ["GEMINI_API_KEY"] == ak.current_key()


def test_get_status_missing_and_cached(monkeypatch):
    name = _stub_settings(monkeypatch)
    calls = []
    monkeypatch.setattr(ak, "check_key", lambda k: calls.append(k) or {"state": "ok", "message": "m"})
    ak._cache.update(at=0.0, data=None, ttl=0)
    assert ak.get_status()["state"] == "ok" and ak.get_status()["state"] == "ok" and len(calls) == 1
    ak.get_status(force=True)
    assert len(calls) == 2
    monkeypatch.setattr(settings, name, "")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ak.get_status()["state"] == "missing"


def test_api_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(ak, "get_status", lambda force=False: {"state": "invalid", "message": "m", "masked": "AIza...x"})

    def fake_set(raw):
        if raw == "bad":
            raise ValueError("kaam nahi kar rahi")
        return {"state": "ok", "message": "save", "masked": "AIza...y"}

    monkeypatch.setattr(ak, "set_key", fake_set)
    c = TestClient(create_app(db_path=tmp_path / "t.db", runner=lambda **kw: None, auto_publish=False, auto_produce=False))
    assert c.get("/settings/gemini").json()["state"] == "invalid"
    assert c.post("/settings/gemini", json={"key": "good"}).json()["state"] == "ok"
    r = c.post("/settings/gemini", json={"key": "bad"})
    assert r.status_code == 422 and "kaam nahi" in r.json()["detail"]


def test_api_client_gemini_calls():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.url.query.decode()))
        return httpx.Response(200, json={"state": "ok"})

    c = ApiClient("http://x", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert c.gemini_status(force=True) == {"state": "ok"} and c.set_gemini_key("k") == {"state": "ok"}
    assert seen == [("GET", "/settings/gemini", "force=true"), ("POST", "/settings/gemini", "")]
