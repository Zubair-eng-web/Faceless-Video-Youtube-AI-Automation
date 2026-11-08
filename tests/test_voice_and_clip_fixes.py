from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard
from app.services import tts
from app.services.pixabay import SceneClip
from app.services.tts import (
    SceneAudio,
    TTSError,
    Voiceover,
    WordTiming,
    generate_voiceover,
    silence_trim,
    trim_audio,
)
from app.services.video_editor import detect_leading_black, render_video, segment_args


def w(text, start, end):
    return WordTiming(text=text, start=start, end=end)


def one_scene_board():
    return build_storyboard(
        ScriptDraft(
            title="T",
            hook="h",
            scenes=[SceneDraft(narration="one two", visual_description="v", search_query="q")],
        )
    )


def concat(paths, out):
    Path(out).write_bytes(b"x")


# ---------- silence_trim ----------
def test_silence_trim_is_none_for_tight_audio():
    assert silence_trim([w("a", 0.0, 1.0), w("b", 1.0, 3.0)], 3.0) is None


def test_silence_trim_cuts_leading_and_trailing_silence():
    assert silence_trim([w("a", 0.9, 1.2), w("b", 1.3, 4.8)], 6.4) == (0.8, 4.4)


def test_generate_voiceover_trims_silence_and_shifts_words(tmp_path):
    state = {"duration": 6.4}
    trims = []

    async def synth(text, voice, rate, path):
        Path(path).write_bytes(b"audio")
        return [w("a", 0.9, 1.2), w("b", 1.3, 4.8)]

    def trim_fn(path, start, length):
        trims.append((Path(path).name, start, length))
        state["duration"] = length

    vo = generate_voiceover(one_scene_board(), tmp_path, synth=synth, duration_fn=lambda p: state["duration"],
                            concat_fn=concat, trim_fn=trim_fn)
    assert trims == [("scene_01.mp3", 0.8, 4.4)]
    assert vo.duration == 4.4
    assert [(x.start, x.end) for x in vo.words] == [(0.1, 0.4), (0.5, 4.0)]


def test_generate_voiceover_does_not_trim_estimated_timings(tmp_path):
    async def synth(text, voice, rate, path):
        Path(path).write_bytes(b"audio")
        return []

    def trim_fn(path, start, length):
        raise AssertionError("trim nahi hona chahiye")

    vo = generate_voiceover(one_scene_board(), tmp_path, synth=synth, duration_fn=lambda p: 5.0,
                            concat_fn=concat, trim_fn=trim_fn)
    assert vo.duration == 5.0


# ---------- trim_audio ----------
def test_trim_audio_replaces_the_file(monkeypatch, tmp_path):
    audio = tmp_path / "scene_01.mp3"
    audio.write_bytes(b"old")
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        Path(args[-1]).write_bytes(b"new")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(tts.subprocess, "run", fake_run)
    trim_audio(audio, 0.8, 4.4)
    assert audio.read_bytes() == b"new"
    assert not (tmp_path / "scene_01.trim.mp3").exists()
    assert "0.800" in seen["args"] and "4.400" in seen["args"]


def test_trim_audio_failure_keeps_original(monkeypatch, tmp_path):
    audio = tmp_path / "scene_01.mp3"
    audio.write_bytes(b"old")
    monkeypatch.setattr(tts.subprocess, "run", lambda args, **kw: SimpleNamespace(returncode=1, stderr="boom"))
    with pytest.raises(TTSError):
        trim_audio(audio, 0.8, 4.4)
    assert audio.read_bytes() == b"old"


# ---------- clip ke shuru ka kala hissa ----------
def test_segment_args_skips_leading_black_before_input():
    args = segment_args("in.mp4", 3.0, "out.mp4", 1080, 1920, 30, 21, start=0.6)
    assert args[args.index("-ss") + 1] == "0.60"
    assert args.index("-ss") < args.index("-i")


def test_segment_args_without_start_has_no_ss():
    assert "-ss" not in segment_args("in.mp4", 3.0, "out.mp4", 1080, 1920, 30, 21)


def runner_with(stderr):
    return lambda args, **kwargs: SimpleNamespace(returncode=0, stderr=stderr)


def test_detect_leading_black_reads_end_of_leading_segment():
    log = "[blackdetect @ 0x1] black_start:0 black_end:0.64 black_duration:0.64\n"
    assert detect_leading_black("c.mp4", runner=runner_with(log)) == 0.64


def test_detect_ignores_black_later_in_the_clip():
    log = "[blackdetect @ 0x1] black_start:1.5 black_end:2.0 black_duration:0.5\n"
    assert detect_leading_black("c.mp4", runner=runner_with(log)) == 0.0


def test_detect_ignores_fully_black_clip():
    log = "[blackdetect @ 0x1] black_start:0 black_end:3 black_duration:3\n"
    assert detect_leading_black("c.mp4", runner=runner_with(log)) == 0.0


def test_detect_survives_missing_ffmpeg():
    def boom(args, **kwargs):
        raise OSError("ffmpeg nahi")

    assert detect_leading_black("c.mp4", runner=boom) == 0.0


def test_render_video_skips_leading_black_of_clips(tmp_path):
    vo = Voiceover(path=str(tmp_path / "vo.mp3"), voice="v", duration=2.0,
                   scenes=[SceneAudio(number=1, path="a", start_offset=0.0, duration=2.0,
                                      words=[w("one", 0.0, 1.0)])])
    clips = [SceneClip(scene_number=1, clip_id=1, path=str(tmp_path / "c1.mp4"), query="q",
                       width=1080, height=1920, duration=10, portrait=True, page_url="")]
    calls = []

    def recorder(args, cwd=None):
        calls.append(args)
        out = Path(args[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")

    render_video(one_scene_board(), clips, vo, tmp_path / "out", music_dir=tmp_path / "nomusic",
                 fonts_dir=tmp_path / "nofonts", runner=recorder, black_fn=lambda p: 0.6)
    assert "-ss" in calls[0] and "0.60" in calls[0]
