from pathlib import Path

from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard
from app.services.captions import build_ass
from app.services.pixabay import SceneClip
from app.services.quality import (
    check_video,
    parse_ass_dialogues,
    parse_black_segments,
    parse_mean_volume,
    parse_silences,
)
from app.services.tts import SceneAudio, Voiceover, WordTiming

GOOD_LOG = "mean_volume: -20.1 dB\nmax_volume: -3.0 dB\n"


def good_probe(path):
    return {"width": 1080, "height": 1920, "duration": 5.0, "has_audio": True}


def good_analyze(path):
    return GOOD_LOG


def setup(tmp_path):
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
        path="x.mp3",
        voice="v",
        duration=5.0,
        scenes=[
            SceneAudio(number=1, path="a", start_offset=0.0, duration=3.0, words=[WordTiming(text="one", start=0.0, end=1.0)]),
            SceneAudio(number=2, path="b", start_offset=3.0, duration=2.0, words=[WordTiming(text="four", start=0.0, end=1.0)]),
        ],
    )
    clips = []
    for i in (1, 2):
        clip_file = tmp_path / f"c{i}.mp4"
        clip_file.write_bytes(b"x")
        clips.append(SceneClip(scene_number=i, clip_id=i, path=str(clip_file), query="q",
                               width=1080, height=1920, duration=10, portrait=True, page_url=""))
    video = tmp_path / "video.mp4"
    video.write_bytes(b"x")
    captions = tmp_path / "captions.ass"
    captions.write_text(build_ass(vo.words), encoding="utf-8")
    return board, vo, clips, video, captions


def run(tmp_path, probe=good_probe, analyze=good_analyze, clips=None, captions=None, video=None):
    board, vo, base_clips, base_video, base_captions = setup(tmp_path)
    return check_video(video or base_video, vo, board, clips if clips is not None else base_clips,
                       captions or base_captions, probe=probe, analyze=analyze)


def codes(report):
    return [i.code for i in report.issues]


def test_parse_black_segments():
    log = "[blackdetect @ 0x1] black_start:1.5 black_end:2.5 black_duration:1\n"
    assert parse_black_segments(log) == [(1.5, 2.5)]


def test_parse_silences_with_end():
    log = "[silencedetect @ 0x1] silence_start: 3.2\n[silencedetect @ 0x1] silence_end: 5.7 | silence_duration: 2.5\n"
    assert parse_silences(log, 10.0) == [(3.2, 2.5)]


def test_parse_silences_trailing_without_end():
    assert parse_silences("[silencedetect @ 0x1] silence_start: 4.0\n", 5.0) == [(4.0, 1.0)]


def test_parse_mean_volume():
    assert parse_mean_volume("mean_volume: -20.1 dB") == -20.1
    assert parse_mean_volume("mean_volume: -inf dB") == float("-inf")
    assert parse_mean_volume("nothing here") is None


def test_parse_ass_dialogues():
    text = "Dialogue: 0,0:00:01.50,0:00:02.00,Default,,0,0,0,,{x}A\nStyle: ignore\n"
    assert parse_ass_dialogues(text) == [(1.5, 2.0)]


def test_good_video_passes_with_no_issues(tmp_path):
    report = run(tmp_path)
    assert report.issues == []
    assert report.passed is True
    assert report.stats["caption_lines"] == 2


def test_missing_video_file(tmp_path):
    report = run(tmp_path, video=tmp_path / "nope.mp4")
    assert codes(report) == ["missing_file"]
    assert report.passed is False


def test_wrong_resolution(tmp_path):
    report = run(tmp_path, probe=lambda p: {"width": 1920, "height": 1080, "duration": 5.0, "has_audio": True})
    assert "resolution" in codes(report)


def test_no_audio_track(tmp_path):
    report = run(tmp_path, probe=lambda p: {"width": 1080, "height": 1920, "duration": 5.0, "has_audio": False})
    assert "no_audio" in codes(report)


def test_duration_mismatch(tmp_path):
    report = run(tmp_path, probe=lambda p: {"width": 1080, "height": 1920, "duration": 8.0, "has_audio": True})
    assert "duration" in codes(report)


def test_black_frames_are_an_error(tmp_path):
    report = run(tmp_path, analyze=lambda p: GOOD_LOG + "[blackdetect @ 0x1] black_start:1 black_end:2 black_duration:1\n")
    assert "black_frames" in codes(report)
    assert report.passed is False


def test_long_silence_is_only_a_warning(tmp_path):
    log = GOOD_LOG + "[silencedetect @ 0x1] silence_end: 4.0 | silence_duration: 2.0\n"
    report = run(tmp_path, analyze=lambda p: log)
    assert codes(report) == ["long_silence"]
    assert report.passed is True


def test_quiet_audio_warning(tmp_path):
    report = run(tmp_path, analyze=lambda p: "mean_volume: -35.0 dB\n")
    assert codes(report) == ["quiet_audio"]
    assert report.passed is True


def test_silent_audio_is_an_error(tmp_path):
    report = run(tmp_path, analyze=lambda p: "mean_volume: -inf dB\n")
    assert "silent_audio" in codes(report)


def test_missing_clip_for_a_scene(tmp_path):
    board, vo, clips, video, captions = setup(tmp_path)
    report = check_video(video, vo, board, clips[:1], captions, probe=good_probe, analyze=good_analyze)
    assert "missing_clip" in codes(report)


def test_caption_count_mismatch(tmp_path):
    board, vo, clips, video, captions = setup(tmp_path)
    captions.write_text(build_ass(vo.words[:1]), encoding="utf-8")
    report = check_video(video, vo, board, clips, captions, probe=good_probe, analyze=good_analyze)
    assert "caption_count" in codes(report)


def test_missing_captions_file(tmp_path):
    report = run(tmp_path, captions=tmp_path / "nope.ass")
    assert "no_captions" in codes(report)


def test_analysis_failure_is_reported(tmp_path):
    def boom(path):
        raise RuntimeError("ffmpeg crash")

    report = run(tmp_path, analyze=boom)
    assert "analysis_failed" in codes(report)
    assert report.passed is False
