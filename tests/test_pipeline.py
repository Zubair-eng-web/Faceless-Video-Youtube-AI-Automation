import json
from datetime import datetime
from pathlib import Path

import pytest

from app.agents.seo_agent import SEOPack
from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard
from app.pipeline import PipelineError, run_pipeline, slugify
from app.services.pixabay import SceneClip
from app.services.quality import Issue, QualityReport
from app.services.tts import SceneAudio, Voiceover, WordTiming


def make_board():
    return build_storyboard(
        ScriptDraft(
            title="T",
            hook="h",
            scenes=[
                SceneDraft(narration="one two three", visual_description="v", search_query="q"),
                SceneDraft(narration="four five", visual_description="v", search_query="q"),
            ],
        )
    )


def make_voiceover(out_dir):
    return Voiceover(
        path=str(Path(out_dir) / "voiceover.mp3"),
        voice="v",
        duration=5.0,
        scenes=[
            SceneAudio(number=1, path="a", start_offset=0.0, duration=3.0, words=[WordTiming(text="one", start=0.0, end=1.0)]),
            SceneAudio(number=2, path="b", start_offset=3.0, duration=2.0, words=[WordTiming(text="four", start=0.0, end=1.0)]),
        ],
    )


class Fakes:
    def __init__(self, fail_at=None, quality_ok=True):
        self.calls = []
        self.fail_at = fail_at
        self.quality_ok = quality_ok
        self.clip_durations = None

    def _enter(self, name):
        self.calls.append(name)
        if self.fail_at == name:
            raise RuntimeError(f"{name} toot gaya")

    def script(self, topic, client, language="English", target_seconds=40):
        self._enter("script")
        return make_board()

    def voiceover(self, board, out_dir, voice=None):
        self._enter("voiceover")
        return make_voiceover(out_dir)

    def clips(self, board, client):
        self._enter("clips")
        self.clip_durations = [s.duration for s in board.scenes]
        return [
            SceneClip(scene_number=i, clip_id=i, path=f"c{i}.mp4", query="q", width=1080, height=1920,
                      duration=10, portrait=True, page_url="")
            for i in (1, 2)
        ]

    def render(self, board, clips, vo, out_dir):
        self._enter("render")
        out_dir = Path(out_dir)
        (out_dir / "segments").mkdir(parents=True, exist_ok=True)
        (out_dir / "segments" / "seg_01.mp4").write_bytes(b"x")
        video = out_dir / "video.mp4"
        video.write_bytes(b"x")
        return video

    def seo(self, board, client):
        self._enter("seo")
        return SEOPack(title="Title", description="Desc", hashtags=["#Shorts"], tags=["t"], thumbnail_text="BOOM")

    def frame(self, video, at, out):
        self._enter("frame")
        Path(out).write_bytes(b"x")
        return Path(out)

    def thumb(self, frame, text, out, font_path=None):
        self._enter("thumb")
        Path(out).write_bytes(b"x")
        return Path(out)

    def check(self, video, vo, board, clips, captions_path):
        self._enter("check")
        issues = [] if self.quality_ok else [Issue(level="error", code="black_frames", message="kala")]
        return QualityReport(issues=issues, stats={})


def run(tmp_path, fakes, progress=None, topic="Black Holes!"):
    return run_pipeline(
        topic, gemini=object(), http=object(), out_root=tmp_path,
        progress=progress or (lambda message: None),
        now=lambda: datetime(2026, 11, 6, 7, 30, 0),
        script_fn=fakes.script, voiceover_fn=fakes.voiceover, clips_fn=fakes.clips,
        render_fn=fakes.render, seo_fn=fakes.seo, frame_fn=fakes.frame,
        thumb_fn=fakes.thumb, check_fn=fakes.check,
    )


def test_slugify():
    assert slugify("Black Holes: Truth!") == "black_holes_truth"
    assert slugify("!!!") == "video"
    assert len(slugify("a" * 100)) <= 40


def test_pipeline_runs_steps_in_order(tmp_path):
    fakes = Fakes()
    run(tmp_path, fakes)
    assert fakes.calls == ["script", "voiceover", "clips", "render", "seo", "frame", "thumb", "check"]


def test_pipeline_saves_files_and_result(tmp_path):
    result = run(tmp_path, Fakes())
    run_dir = Path(result.run_dir)
    assert run_dir.name == "20261106_073000_black_holes"
    for name in ("storyboard.json", "voiceover.json", "clips.json", "seo.json", "quality.json", "result.json"):
        assert (run_dir / name).exists(), name
    saved = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert saved["status"] == "ready"
    assert saved["seo"]["title"] == "Title"
    assert result.title == "Title"
    assert result.duration == 5.0


def test_clips_are_chosen_with_real_voiceover_durations(tmp_path):
    fakes = Fakes()
    run(tmp_path, fakes)
    assert fakes.clip_durations == [3.0, 2.0]


def test_quality_failure_marks_needs_review(tmp_path):
    result = run(tmp_path, Fakes(quality_ok=False))
    assert result.status == "needs_review"
    assert result.quality.errors[0].code == "black_frames"


def test_failed_step_is_named_and_later_steps_do_not_run(tmp_path):
    fakes = Fakes(fail_at="voiceover")
    with pytest.raises(PipelineError) as info:
        run(tmp_path, fakes)
    assert info.value.step == "voiceover"
    assert "voiceover toot gaya" in str(info.value)
    assert "clips" not in fakes.calls


def test_thumbnail_failure_is_reported_as_thumbnail_step(tmp_path):
    with pytest.raises(PipelineError) as info:
        run(tmp_path, Fakes(fail_at="thumb"))
    assert info.value.step == "thumbnail"


def test_empty_topic_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        run(tmp_path, Fakes(), topic="   ")


def test_progress_reports_seven_steps(tmp_path):
    messages = []
    run(tmp_path, Fakes(), progress=messages.append)
    assert len([m for m in messages if m.startswith('[')]) == 7
    assert messages[0].startswith("[1/7]")
    assert messages[-1].startswith("[7/7]")
