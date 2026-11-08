"""Task 27: visual report, credits aur author tracking (asli API nahi, sab fake)."""
from app.core.models import Scene, Storyboard
from app.services import pixabay as px
from app.services.long_visuals import build_credits, build_visual_report, credits_text, save_visuals
from app.services.pixabay import SceneClip


def make_board(n=5):
    scenes = [Scene(number=i + 1, narration="n", visual_description="v", search_query=f"q{i}", duration=7)
              for i in range(n)]
    return Storyboard(title="T", hook="h", scenes=scenes)


def make_clip(num, cid, query=None, w=1920, h=1080, dur=10, author="alice"):
    return SceneClip(scene_number=num, clip_id=cid, path="x.mp4", query=query or f"q{num - 1}", width=w, height=h,
                     duration=dur, portrait=h > w, page_url=f"https://pixabay.com/v/{cid}", author=author)


def test_parse_hit_keeps_author():
    hit = {"id": 1, "user": "alice", "pageURL": "u", "tags": "a", "duration": 10,
           "videos": {"large": {"url": "x", "width": 1920, "height": 1080}}}
    assert px.parse_hit(hit).author == "alice"
    hit.pop("user")
    assert px.parse_hit(hit).author == ""


def test_old_clips_json_still_loads():
    c = SceneClip.model_validate({"scene_number": 1, "clip_id": 5, "path": "p", "query": "q", "width": 1920,
                                  "height": 1080, "duration": 9.0, "portrait": False, "page_url": "u"})
    assert c.author == "" and c.provider == "Pixabay" and c.license == "Pixabay License"


def test_clean_report_has_no_warnings():
    rep = build_visual_report(make_board(), [make_clip(i, i) for i in range(1, 6)])
    assert rep.ok and rep.with_clip == 5 and rep.unique_clips == 5 and not rep.warnings


def test_missing_scene_is_not_ok():
    clips = [make_clip(i, i) for i in (1, 2, 4, 5)]
    rep = build_visual_report(make_board(), clips)
    assert not rep.ok and rep.missing == [3] and rep.warnings


def test_reuse_and_back_to_back():
    clips = [make_clip(1, 1), make_clip(2, 1, query="q1"), make_clip(3, 2), make_clip(4, 3), make_clip(5, 4)]
    rep = build_visual_report(make_board(), clips)
    assert rep.reused == [2] and rep.back_to_back == [2]
    assert any("Lagatar" in w for w in rep.warnings)


def test_fallback_and_generic_queries():
    clips = [make_clip(1, 1, query="q0 extra"), make_clip(2, 2, query="T"), make_clip(3, 3), make_clip(4, 4),
             make_clip(5, 5)]
    rep = build_visual_report(make_board(), clips)
    assert rep.fallback == [1] and rep.generic == [2]


def test_portrait_and_too_short():
    clips = [make_clip(1, 1, w=1080, h=1920), make_clip(2, 2, dur=3), make_clip(3, 3), make_clip(4, 4),
             make_clip(5, 5)]
    rep = build_visual_report(make_board(), clips)
    assert rep.portrait == [1] and rep.too_short == [2]


def test_credits_group_and_text(tmp_path):
    clips = [make_clip(1, 1, author="alice"), make_clip(2, 1, author="alice"), make_clip(3, 2, author="bob")]
    credits = build_credits(clips)
    assert len(credits) == 2 and credits[0].scenes == [1, 2]
    text = credits_text(credits)
    assert "Pixabay" in text and "alice" in text and "bob" in text
    assert credits_text([]) == ""
    rep, cr = save_visuals(tmp_path, make_board(3), clips)
    assert (tmp_path / "visual_report.json").exists() and (tmp_path / "visual_credits.json").exists()