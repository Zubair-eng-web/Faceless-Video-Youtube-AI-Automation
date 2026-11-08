from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard
from app.services.pixabay import SceneClip
from app.services.tts import SceneAudio, Voiceover, WordTiming
from app.services.video_editor import (
    VideoError,
    build_filter_complex,
    pick_music,
    prepare_fonts,
    render_video,
    segment_args,
)


def test_filter_complex_offsets_and_transition_cycle():
    fc = build_filter_complex([3.0, 2.0, 4.0], transition=0.3)
    assert "xfade=transition=fade:duration=0.300:offset=3.000[v1]" in fc
    assert "xfade=transition=slideleft:duration=0.300:offset=5.000[v2]" in fc
    assert "[v2]ass=captions.ass[vout]" in fc
    assert "[3:a]" in fc  # voiceover scenes ke baad wala input


def test_filter_complex_single_scene_has_no_xfade():
    fc = build_filter_complex([4.0])
    assert "xfade" not in fc
    assert "[0:v]ass=captions.ass[vout]" in fc


def test_filter_complex_with_music_mixes_audio():
    fc = build_filter_complex([3.0, 2.0], music=True, music_volume=0.12)
    assert "amix=inputs=2" in fc
    assert "[3:a]" in fc  # music input: 2 scenes + 1 voiceover ke baad
    assert "volume=0.120" in fc


def test_filter_complex_without_music_has_no_amix():
    assert "amix" not in build_filter_complex([3.0, 2.0], music=False)


def test_filter_complex_clamps_long_transition():
    fc = build_filter_complex([1.0, 1.0], transition=0.5)
    assert "duration=0.400" in fc


def test_filter_complex_uses_fonts_dir_when_available():
    assert "ass=captions.ass:fontsdir=fonts" in build_filter_complex([3.0], fonts=True)


def test_segment_args_crops_to_vertical_and_loops():
    args = segment_args("in.mp4", 3.3, "out.mp4", 1080, 1920, 30, 21)
    assert "-stream_loop" in args
    assert any("crop=1080:1920" in a for a in args)
    assert "3.300" in args
    assert args[-1] == "out.mp4"


def test_pick_music_chooses_only_audio_files(tmp_path):
    (tmp_path / "b.mp3").write_bytes(b"x")
    (tmp_path / "a.wav").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    rng = SimpleNamespace(choice=lambda items: items[0])
    assert pick_music(tmp_path, rng=rng).name == "a.wav"


def test_pick_music_returns_none_when_empty_or_missing(tmp_path):
    assert pick_music(tmp_path) is None
    assert pick_music(tmp_path / "nope") is None


def test_prepare_fonts_copies_ttf(tmp_path):
    fonts = tmp_path / "fonts_src"
    fonts.mkdir()
    (fonts / "a.ttf").write_bytes(b"x")
    (fonts / "readme.txt").write_text("x")
    work = tmp_path / "work"
    work.mkdir()
    assert prepare_fonts(fonts, work) is True
    assert (work / "fonts" / "a.ttf").exists()
    assert prepare_fonts(tmp_path / "empty", work) is False


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, args, cwd=None):
        self.calls.append((args, cwd))
        out = Path(args[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")


def make_inputs(tmp_path):
    board = build_storyboard(
        ScriptDraft(
            title="T",
            hook="h",
            scenes=[
                SceneDraft(narration="one two three", visual_description="v", search_query="q"),
                SceneDraft(narration="four five", visual_description="v", search_query="q"),
            ],
        )
    )
    vo = Voiceover(
        path=str(tmp_path / "voiceover.mp3"),
        voice="v",
        duration=5.0,
        scenes=[
            SceneAudio(number=1, path="a", start_offset=0.0, duration=3.0, words=[WordTiming(text="one", start=0.0, end=1.0)]),
            SceneAudio(number=2, path="b", start_offset=3.0, duration=2.0, words=[WordTiming(text="four", start=0.0, end=1.0)]),
        ],
    )
    clips = [
        SceneClip(scene_number=i, clip_id=i, path=str(tmp_path / f"c{i}.mp4"), query="q",
                  width=1080, height=1920, duration=10, portrait=True, page_url="")
        for i in (1, 2)
    ]
    return board, vo, clips


def test_render_video_builds_segments_then_final(tmp_path):
    board, vo, clips = make_inputs(tmp_path)
    rec = Recorder()
    out = tmp_path / "out"
    video = render_video(board, clips, vo, out, music_dir=tmp_path / "nomusic",
                         fonts_dir=tmp_path / "nofonts", runner=rec)
    assert video.name == "video.mp4"
    assert len(rec.calls) == 3
    assert "3.300" in rec.calls[0][0]  # pehla scene: 3.0 + transition 0.3
    assert "2.000" in rec.calls[1][0]  # aakhri scene me transition add nahi hoti
    final_args, cwd = rec.calls[2]
    assert "-filter_complex" in final_args
    assert "5.000" in final_args
    assert cwd == out
    assert "ONE" in (out / "captions.ass").read_text(encoding="utf-8")


def test_render_video_raises_when_a_clip_is_missing(tmp_path):
    board, vo, clips = make_inputs(tmp_path)
    with pytest.raises(VideoError):
        render_video(board, clips[:1], vo, tmp_path / "out", runner=Recorder())
