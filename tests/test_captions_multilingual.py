from pathlib import Path

from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard
from app.services.captions import build_ass, group_words
from app.services.pixabay import SceneClip
from app.services.tts import SceneAudio, Voiceover, WordTiming
from app.services.video_editor import render_video

HINDI = "\u0928\u092e\u0938\u094d\u0924\u0947"
HINDI_END = HINDI + "\u0964"
URDU_END = "\u0628\u0627\u062a\u06d4"


def w(text, start, end):
    return WordTiming(text=text, start=start, end=end)


class Recorder:
    def __call__(self, args, cwd=None):
        out = Path(args[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")


def test_hindi_danda_ends_a_caption_group():
    words = [w(HINDI_END, 0, 1), w("a", 1, 2), w("b", 2, 3)]
    assert [len(g) for g in group_words(words, max_words=3)] == [1, 2]


def test_urdu_full_stop_ends_a_caption_group():
    words = [w(URDU_END, 0, 1), w("a", 1, 2)]
    assert [len(g) for g in group_words(words, max_words=3)] == [1, 1]


def test_build_ass_uses_given_font_and_keeps_hindi_text():
    ass = build_ass([w(HINDI, 0.0, 1.0)], font="Noto Sans Devanagari", font_size=84, uppercase=False)
    assert "Style: Default,Noto Sans Devanagari,84," in ass
    assert HINDI in ass


def test_render_video_uses_language_font(tmp_path):
    board = build_storyboard(
        ScriptDraft(
            title="T",
            hook="h",
            scenes=[SceneDraft(narration="one two", visual_description="v", search_query="q")],
        ),
        language="Hindi",
    )
    vo = Voiceover(
        path=str(tmp_path / "vo.mp3"),
        voice="v",
        duration=2.0,
        scenes=[SceneAudio(number=1, path="a", start_offset=0.0, duration=2.0, words=[w(HINDI, 0.0, 1.0)])],
    )
    clips = [SceneClip(scene_number=1, clip_id=1, path=str(tmp_path / "c1.mp4"), query="q",
                       width=1080, height=1920, duration=10, portrait=True, page_url="")]
    out = tmp_path / "out"
    render_video(board, clips, vo, out, music_dir=tmp_path / "nomusic", fonts_dir=tmp_path / "nofonts",
                 runner=Recorder())
    ass = (out / "captions.ass").read_text(encoding="utf-8")
    assert "Noto Sans Devanagari" in ass
    assert HINDI in ass
