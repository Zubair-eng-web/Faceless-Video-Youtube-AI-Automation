from app.core.config import Settings
from app.services import long_render, video_editor
from app.services.captions import build_ass


def test_default_profiles_are_portrait_and_landscape():
    f = Settings.model_fields
    assert (f["video_width"].default, f["video_height"].default) == (1080, 1920)
    assert (f["long_video_width"].default, f["long_video_height"].default) == (1920, 1080)


def test_segment_args_per_profile():
    short = " ".join(video_editor.segment_args("c.mp4", 5, "o.mp4", 1080, 1920, 30, 21))
    long_ = " ".join(video_editor.segment_args("c.mp4", 5, "o.mp4", 1920, 1080, 30, 21))
    assert "crop=1080:1920" in short and "crop=1920:1080" in long_


def test_long_and_shorts_share_helpers():
    assert long_render.segment_args is video_editor.segment_args
    assert long_render.build_ass is build_ass
