from pathlib import Path

from fastapi.testclient import TestClient

from app import pipeline
from app.api.main import create_app
from app.core import db
from app.core.models import Scene, Storyboard


class Fake:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump_json(self, indent=None):
        return "{}"


def _run(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    board = Storyboard(title="T", hook="h", language="English", scenes=[
        Scene(number=1, narration="Hello there", visual_description="v", search_query="q", duration=3.0)])
    (run / "storyboard.json").write_text(board.model_dump_json(), encoding="utf-8")
    return run


def _client(tmp_path, redoer=None, runner=None):
    app = create_app(db_path=tmp_path / "t.db", runner=runner or (lambda **kw: None), redoer=redoer,
                     auto_publish=False, auto_produce=False)
    return TestClient(app), tmp_path / "t.db"


def _video(path, run=None, status="needs_review"):
    vid = db.create_job(path, None, "t", "English")
    if status != "queued":
        db.transition(path, vid, status, {"queued"})
    if run:
        db.set_run_dir(path, vid, str(run))
    return vid


def test_storyboard_and_redo_flow(tmp_path):
    seen = {}

    def fake_redo(run_dir, edits, branding=None):
        seen.update(run_dir=run_dir, edits=edits, branding=branding)
        return Fake(topic="t", status="ready", title="Naya", run_dir=run_dir, video_path="v",
                    thumbnail_path="t", duration=6.0, seo=Fake(), quality=Fake())

    c, path = _client(tmp_path, fake_redo)
    run = _run(tmp_path)
    vid = _video(path, run)
    assert c.get(f"/videos/{vid}/storyboard").json()["scenes"][0]["number"] == 1
    r = c.post(f"/videos/{vid}/redo", json={"edits": [{"scene": 1, "narration": "Naya text"}]})
    assert r.status_code == 202
    assert seen["edits"][0].scene == 1 and seen["branding"] is None and seen["run_dir"] == str(run)
    v = c.get(f"/videos/{vid}").json()
    assert v["status"] == "ready" and v["title"] == "Naya"


def test_redo_failure_marks_failed(tmp_path):
    def boom(run_dir, edits, branding=None):
        raise RuntimeError("boom")

    c, path = _client(tmp_path, boom)
    vid = _video(path, _run(tmp_path))
    assert c.post(f"/videos/{vid}/redo", json={"edits": []}).status_code == 202
    v = c.get(f"/videos/{vid}").json()
    assert v["status"] == "failed" and "boom" in v["error"]


def test_redo_without_run_folder_is_400_and_missing_video_404(tmp_path):
    c, path = _client(tmp_path)
    vid = _video(path)
    assert c.post(f"/videos/{vid}/redo", json={"edits": []}).status_code == 400
    assert c.get(f"/videos/{vid}/storyboard").status_code == 404
    assert c.get("/videos/999/storyboard").status_code == 404


def test_redo_wrong_status_is_409(tmp_path):
    c, path = _client(tmp_path)
    vid = _video(path, _run(tmp_path), status="queued")
    assert c.post(f"/videos/{vid}/redo", json={"edits": []}).status_code == 409


def test_failed_job_remembers_run_dir(tmp_path):
    folder = str(tmp_path / "r")

    def boom(**kw):
        pipeline.LAST_RUN_DIR = folder
        raise RuntimeError("boom")

    c, _ = _client(tmp_path, runner=boom)
    assert c.post("/generate", json={"topic": "x"}).status_code == 202
    v = c.get("/videos").json()[0]
    assert v["status"] == "failed" and v["run_dir"] == folder
