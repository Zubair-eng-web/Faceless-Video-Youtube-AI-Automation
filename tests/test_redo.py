import json
from pathlib import Path

import pytest

from app.agents.seo_agent import SEOPack
from app.core.models import Scene, Storyboard
from app.services import redo
from app.services.fact_check import ClaimCheck, FactCheckReport
from app.services.pixabay import SceneClip
from app.services.redo import RedoError, SceneEdit, apply_edits, load_storyboard_view, redo_run
from app.services.tts import SceneAudio, Voiceover


class Fake:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump_json(self, indent=None):
        return "{}"


@pytest.fixture(autouse=True)
def _fake_result(monkeypatch):
    monkeypatch.setattr(redo, "PipelineResult", Fake)


def _board():
    return Storyboard(title="T", hook="h", language="English", scenes=[
        Scene(number=i, narration=f"Narration {i} here", visual_description="v", search_query=f"q{i}", duration=3.0)
        for i in (1, 2)])


def _vo(run):
    return Voiceover(path=str(Path(run) / "audio" / "vo.mp3"), voice="en-US-AndrewNeural", duration=6.0,
                     scenes=[SceneAudio(number=i, path="x", start_offset=3.0 * (i - 1), duration=3.0, words=[])
                             for i in (1, 2)])


def _clip(n):
    return SceneClip(scene_number=n, clip_id=n, path=f"c{n}.mp4", query=f"q{n}", width=1080, height=1920,
                     duration=10.0, portrait=True, page_url="u")


def _seo():
    return SEOPack(title="Title", description="d", hashtags=["#a"], tags=["t"], thumbnail_text="TT")


def _make_run(tmp_path, voiceover=True, clips=True, seo=True):
    run = tmp_path / "run"
    run.mkdir()
    (run / "storyboard.json").write_text(_board().model_dump_json(), encoding="utf-8")
    if voiceover:
        (run / "voiceover.json").write_text(_vo(run).model_dump_json(), encoding="utf-8")
    if clips:
        (run / "clips.json").write_text("[" + ",".join(_clip(n).model_dump_json() for n in (1, 2)) + "]", encoding="utf-8")
    if seo:
        (run / "seo.json").write_text(_seo().model_dump_json(), encoding="utf-8")
    return run


class Calls:
    def __init__(self, run, wrong=False):
        self.run, self.log, self.wrong = run, [], wrong

    def voiceover(self, board, out_dir, voice=None):
        self.log.append(("voice", board.scenes[0].narration, voice))
        return _vo(self.run)

    def clips(self, board, http):
        self.log.append(("clips", [s.number for s in board.scenes]))
        return [_clip(s.number) for s in board.scenes]

    def render(self, board, clips, vo, run_dir, **kw):
        self.log.append(("render", len(clips)))
        out = Path(run_dir) / "video.mp4"
        out.write_bytes(b"v")
        return out

    def seo(self, board, gemini):
        self.log.append(("seo",))
        return _seo()

    def frame(self, video, t, out):
        Path(out).write_bytes(b"f")
        return Path(out)

    def thumb(self, frame, text, out, font_path=None):
        Path(out).write_bytes(b"t")
        return Path(out)

    def check(self, video, vo, board, clips, ass):
        self.log.append(("check", Path(video).name))
        return Fake(passed=True)

    def fact(self, board, gemini, auto_fix=True):
        self.log.append(("fact", auto_fix))
        claims = [ClaimCheck(scene_number=1, claim="c", verdict="wrong")] if self.wrong else []
        return board, FactCheckReport(claims=claims)

    def kw(self):
        return dict(voiceover_fn=self.voiceover, clips_fn=self.clips, render_fn=self.render, seo_fn=self.seo,
                    frame_fn=self.frame, thumb_fn=self.thumb, check_fn=self.check, fact_fn=self.fact,
                    progress=lambda m: None)


def test_apply_edits():
    b, narr, query = apply_edits(_board(), [SceneEdit(scene=1, narration="Naya  text"),
                                            SceneEdit(scene=2, search_query="ocean")])
    assert narr == {1} and query == {2}
    assert b.scenes[0].narration == "Naya text" and b.scenes[1].search_query == "ocean"
    _, n2, q2 = apply_edits(_board(), [SceneEdit(scene=1, narration="Narration 1  here")])
    assert n2 == set() and q2 == set()
    with pytest.raises(RedoError):
        apply_edits(_board(), [SceneEdit(scene=9, narration="x")])


def test_load_storyboard_view(tmp_path):
    run = _make_run(tmp_path)
    v = load_storyboard_view(run)
    assert v["scenes"][0]["number"] == 1 and v["scenes"][1]["search_query"] == "q2"
    assert load_storyboard_view(None) is None and load_storyboard_view(tmp_path / "nahi") is None


def test_narration_edit_regenerates_voice_fact_and_seo(tmp_path):
    run = _make_run(tmp_path)
    (run / "video_core.mp4").write_bytes(b"old")
    c = Calls(run)
    res = redo_run(run, [SceneEdit(scene=1, narration="  New   text here ")], http=object(), gemini=object(), **c.kw())
    assert [x[0] for x in c.log] == ["voice", "fact", "seo", "render", "check"]
    assert c.log[0] == ("voice", "New text here", "en-US-AndrewNeural")
    assert ("fact", False) in c.log and ("check", "video.mp4") in c.log
    assert not (run / "video_core.mp4").exists()
    assert "New text here" in (run / "storyboard.json").read_text(encoding="utf-8")
    assert (run / "voiceover.json").exists() and res.status == "ready" and res.title == "Title"


def test_query_edit_replaces_only_that_clip(tmp_path):
    run = _make_run(tmp_path)
    c = Calls(run)
    redo_run(run, [SceneEdit(scene=2, search_query="ocean")], http=object(), **c.kw())
    assert [x[0] for x in c.log] == ["clips", "render", "check"] and c.log[0] == ("clips", [2])
    assert len(json.loads((run / "clips.json").read_text(encoding="utf-8"))) == 2
    assert "ocean" in (run / "storyboard.json").read_text(encoding="utf-8")


def test_no_edits_only_rerenders(tmp_path):
    run = _make_run(tmp_path)
    c = Calls(run)
    redo_run(run, [], **c.kw())
    assert [x[0] for x in c.log] == ["render", "check"]


def test_resume_builds_missing_parts(tmp_path):
    run = _make_run(tmp_path, voiceover=False, clips=False, seo=False)
    c = Calls(run)
    redo_run(run, [], http=object(), gemini=object(), **c.kw())
    assert [x[0] for x in c.log] == ["voice", "clips", "seo", "render", "check"]
    assert c.log[1] == ("clips", [1, 2])


def test_missing_seo_without_gemini_fails(tmp_path):
    run = _make_run(tmp_path, seo=False)
    with pytest.raises(RedoError):
        redo_run(run, [], **Calls(run).kw())


def test_unresolved_wrong_claim_needs_review(tmp_path):
    run = _make_run(tmp_path)
    res = redo_run(run, [SceneEdit(scene=1, narration="Something new here")], http=object(), gemini=object(),
                   **Calls(run, wrong=True).kw())
    assert res.status == "needs_review"
