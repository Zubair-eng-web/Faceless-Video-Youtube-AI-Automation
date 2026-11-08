import pytest

from app.core.models import Storyboard
from app.services import long_script as ls
from app.services.long_script import (ChapterDraft, ChapterPlan, LongConfig, LongScriptError, Outline,
                                      SceneDraft, chapter_count, chapter_targets, generate_long_script,
                                      split_scene)

CFG = LongConfig(words_per_minute=100, scene_seconds=6, max_scene_words=30, min_minutes=1, max_minutes=20)


def _outline(n=4):
    return Outline(title="Big Title", hook="Hook line here.",
                   chapters=[ChapterPlan(title=f"Ch{i}", summary="s", key_points=["a", "b"]) for i in range(1, n + 1)])


def _scenes(count, words=10):
    return ChapterDraft(scenes=[SceneDraft(narration=" ".join(["word"] * words) + ".", visual_description="v",
                                           search_query=f"q{i}") for i in range(count)])


class Fake:
    def __init__(self, outline=None, chapters=None):
        self.outline = outline or _outline()
        self.chapters = chapters  # list of drafts, ek call ek item; None = hamesha 5 scenes
        self.calls, self.prompts = [], []

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.calls.append(schema.__name__)
        self.prompts.append(prompt)
        if schema is Outline:
            return self.outline
        if self.chapters:
            return self.chapters.pop(0)
        return _scenes(5)


def test_counts_and_targets():
    assert chapter_count(10) == 5 and chapter_count(20) == 10 and chapter_count(3) == 4 and chapter_count(40) == 10
    t = chapter_targets(1500, 5)
    assert len(t) == 5 and t[0] < t[2] and t[0] == t[4] and abs(sum(t) - 1500) < 6


def test_split_scene():
    assert split_scene("Short one.", 30) == ["Short one."]
    text = ("One two three four five. " * 4).strip()
    parts = split_scene(text, 12)
    assert len(parts) == 2 and all(len(p.split()) <= 12 for p in parts) and split_scene("", 5) == []


def test_generate_builds_storyboard_and_chapters():
    f = Fake()
    r = generate_long_script("Black holes", f, minutes=2, cfg=CFG, progress=lambda m: None)
    assert f.calls == ["Outline"] + ["ChapterDraft"] * 4
    b = r.storyboard
    assert isinstance(b, Storyboard) and b.title == "Big Title" and len(b.scenes) == 20
    assert [s.number for s in b.scenes] == list(range(1, 21)) and b.scenes[0].duration == 6.0
    assert [(c.first_scene, c.last_scene) for c in r.chapters] == [(1, 5), (6, 10), (11, 15), (16, 20)]
    assert r.words == 200 and r.warnings == []
    assert "Hook line here." in f.prompts[1] and "FIRST chapter" in f.prompts[1]
    assert "LAST chapter" in f.prompts[4] and "previous chapter ended" in f.prompts[2]
    assert f.prompts[2].count("Ch2") >= 1


def test_minutes_are_clamped():
    cfg = LongConfig(min_minutes=3, max_minutes=20)
    assert ls.clamp_minutes(1, cfg) == 3 and ls.clamp_minutes(60, cfg) == 20 and ls.clamp_minutes(10, cfg) == 10


def test_short_chapter_is_retried_once():
    f = Fake(chapters=[_scenes(1, 3), _scenes(5), _scenes(5), _scenes(5), _scenes(5)])
    r = generate_long_script("T", f, minutes=2, cfg=CFG, progress=lambda m: None)
    assert f.calls.count("ChapterDraft") == 5 and r.warnings == []
    assert "IMPORTANT" in f.prompts[2]


def test_hopeless_chapter_raises():
    f = Fake(chapters=[_scenes(1, 2), _scenes(1, 2)])
    with pytest.raises(LongScriptError):
        generate_long_script("T", f, minutes=2, cfg=CFG, progress=lambda m: None)


def test_borderline_chapter_accepted_with_warning():
    # target ~44 words; 25 words 0.4x se upar lekin 0.6x se neeche
    f = Fake(chapters=[_scenes(1, 25), _scenes(1, 25)] + [_scenes(5)] * 3)
    r = generate_long_script("T", f, minutes=2, cfg=CFG, progress=lambda m: None)
    assert len(r.warnings) == 1 and "Chapter 1" in r.warnings[0]


def test_too_few_chapters_raises():
    f = Fake(outline=_outline(2))
    with pytest.raises(LongScriptError):
        generate_long_script("T", f, minutes=2, cfg=CFG, progress=lambda m: None)
    assert f.calls == ["Outline", "Outline"]


def test_long_scenes_are_split():
    long = ChapterDraft(scenes=[SceneDraft(narration=" ".join(["Sentence number %d is here." % i for i in range(20)]),
                                           visual_description="v", search_query="q")])
    f = Fake(chapters=[long] + [_scenes(5)] * 3)
    cfg = CFG.model_copy(update={"max_scene_words": 12})
    r = generate_long_script("T", f, minutes=2, cfg=cfg, progress=lambda m: None)
    first = r.chapters[0]
    assert first.last_scene - first.first_scene + 1 > 3


def test_resume_reuses_saved_files(tmp_path):
    f1 = Fake()
    generate_long_script("T", f1, minutes=2, cfg=CFG, run_dir=tmp_path, progress=lambda m: None)
    assert (tmp_path / "long_outline.json").exists() and (tmp_path / "long_chapter_04.json").exists()
    assert (tmp_path / "storyboard.json").exists()
    (tmp_path / "long_chapter_03.json").unlink()  # beech mein fail hua maan lo
    f2 = Fake()
    generate_long_script("T", f2, minutes=2, cfg=CFG, run_dir=tmp_path, progress=lambda m: None)
    assert f2.calls == ["ChapterDraft"]


def test_empty_topic_and_env_config(monkeypatch):
    with pytest.raises(ValueError):
        generate_long_script("  ", Fake(), cfg=CFG)
    monkeypatch.setenv("LONG_WORDS_PER_MINUTE", "170")
    monkeypatch.setenv("LONG_SCENE_SECONDS", "abc")
    monkeypatch.setenv("LONG_GEMINI_MODEL", "my-model")
    c = LongConfig.from_env()
    assert c.words_per_minute == 170 and c.scene_seconds == 7.0 and c.model == "my-model"
