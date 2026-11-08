"""Video ko uske run folder se dobara banana: script edit, clip badalna, fail hui video ka resume.

Har stage pehle se bani file (voiceover.json, clips.json, seo.json) dobara use karta hai.
Narration badli ho to voiceover dobara banti hai, query badli ho to sirf us scene ki clip.
"""
import json
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from app import pipeline as P
from app.agents.seo_agent import SEOPack
from app.core.models import Storyboard
from app.pipeline import PipelineResult, _save, _step, core_video
from app.services.fact_check import FactCheckReport
from app.services.pixabay import SceneClip
from app.services.tts import Voiceover, apply_durations


class RedoError(RuntimeError):
    pass


class SceneEdit(BaseModel):
    scene: int
    narration: str | None = None
    search_query: str | None = None


class RedoRequest(BaseModel):
    edits: list[SceneEdit] = Field(default_factory=list)


def _norm(text) -> str:
    return " ".join((text or "").split())


def _load(path, model):
    try:
        return model.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _load_clips(path) -> list[SceneClip]:
    try:
        return [SceneClip.model_validate(c) for c in json.loads(Path(path).read_text(encoding="utf-8"))]
    except (OSError, ValueError):
        return []


def _save_clips(path, clips) -> None:
    Path(path).write_text("[" + ",".join(c.model_dump_json() for c in clips) + "]", encoding="utf-8")


def load_storyboard_view(run_dir) -> dict | None:
    """Dashboard ke edit panel ke liye scenes ki list. Folder ya file na ho to None."""
    if not run_dir:
        return None
    board = _load(Path(run_dir) / "storyboard.json", Storyboard)
    if board is None:
        return None
    return {
        "title": board.title,
        "language": board.language,
        "scenes": [{"number": s.number, "narration": s.narration, "search_query": s.search_query,
                    "visual_description": s.visual_description, "duration": s.duration}
                   for s in board.scenes],
    }


def apply_edits(board, edits):
    """(naya board, narration badli wale scenes, query badli wale scenes)."""
    by = {e.scene: e for e in edits}
    unknown = set(by) - {s.number for s in board.scenes}
    if unknown:
        raise RedoError(f"In scenes ka wujood nahi: {sorted(unknown)}")
    narr, query, scenes = set(), set(), []
    for s in board.scenes:
        e, upd = by.get(s.number), {}
        if e:
            n, q = _norm(e.narration), _norm(e.search_query)
            if n and n != _norm(s.narration):
                upd["narration"] = n
                narr.add(s.number)
            if q and q != _norm(s.search_query):
                upd["search_query"] = q
                query.add(s.number)
        scenes.append(s.model_copy(update=upd) if upd else s)
    return board.model_copy(update={"scenes": scenes}), narr, query


def redo_run(run_dir, edits=(), http=None, gemini=None, branding=None, progress=print,
             voiceover_fn=None, clips_fn=None, render_fn=None, seo_fn=None,
             frame_fn=None, thumb_fn=None, check_fn=None, fact_fn=None) -> PipelineResult:
    voiceover_fn = voiceover_fn or P.generate_voiceover
    clips_fn = clips_fn or P.collect_clips
    render_fn = render_fn or P.render_video
    seo_fn = seo_fn or P.generate_seo
    frame_fn = frame_fn or P.extract_frame
    thumb_fn = thumb_fn or P.make_thumbnail
    check_fn = check_fn or P.check_video
    fact_fn = fact_fn or P.run_fact_check

    run = Path(run_dir)
    board_file = run / "storyboard.json"
    board = _load(board_file, Storyboard)
    if board is None:
        raise RedoError("Storyboard nahi mila, is folder se dobara nahi ban sakti")
    board, narr, query = apply_edits(board, edits)

    old_vo = _load(run / "voiceover.json", Voiceover)
    if narr or query:
        _save(board_file, board)
    if narr:  # purani voiceover ab galat hai (retry par bhi dobara banegi)
        (run / "voiceover.json").unlink(missing_ok=True)
    if query:  # sirf badli hui scenes ki clip hatao, baqi rehti hain
        _save_clips(run / "clips.json", [c for c in _load_clips(run / "clips.json") if c.scene_number not in query])

    vo = None if narr else old_vo
    if vo is None:
        progress("[1/5] Voiceover...")
        vo = _step("voiceover", voiceover_fn, board, run / "audio", voice=old_vo.voice if old_vo else None)
        _save(run / "voiceover.json", vo)

    timed = apply_durations(board, vo)
    clips = _load_clips(run / "clips.json")
    have = {c.scene_number for c in clips}
    need = [s for s in timed.scenes if s.number not in have]
    if need:
        progress(f"[2/5] Clips ({len(need)} scene)...")
        if http is None:
            raise RedoError("Clips ke liye http client chahiye")
        new = _step("clips", clips_fn, timed.model_copy(update={"scenes": need}), http)
        clips = sorted(list(clips) + list(new), key=lambda c: c.scene_number)
        _save_clips(run / "clips.json", clips)

    fact_report = _load(run / "fact_check.json", FactCheckReport)
    if narr and gemini is not None:
        progress("    Fact-check...")
        _, fact_report = fact_fn(board, gemini, auto_fix=False)  # user ka likha text khud nahi badalta
        _save(run / "fact_check.json", fact_report)

    seo = _load(run / "seo.json", SEOPack)
    if gemini is not None and (seo is None or narr):
        try:
            seo = _step("seo", seo_fn, board, gemini)
            _save(run / "seo.json", seo)
        except Exception:  # noqa: BLE001 - purani SEO ho to wahi rakho
            if seo is None:
                raise
    if seo is None:
        raise RedoError("SEO nahi bani aur Gemini bhi nahi mila")

    for name in ("video_core.mp4", "video_branded.mp4"):  # purani intro/outro wali files
        (run / name).unlink(missing_ok=True)
    progress("[3/5] Video render (1-2 minute)...")
    video = _step("render", render_fn, board, clips, vo, run, **({"branding": branding} if branding else {}))

    progress("[4/5] Thumbnail...")
    frame = _step("thumbnail", frame_fn, run / "segments" / "seg_01.mp4", 1.0, run / "thumb_frame.jpg")
    thumb = _step("thumbnail", thumb_fn, frame, seo.thumbnail_text, run / "thumbnail.jpg",
                  font_path=P.settings.fonts_dir / "arialbd.ttf")

    progress("[5/5] Quality check...")
    report = _step("quality", check_fn, core_video(run, video), vo, board, clips, run / "captions.ass")
    _save(run / "quality.json", report)

    try:
        old_result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old_result = {}
    unresolved = bool(fact_report and fact_report.unresolved_wrong)
    result = PipelineResult(
        topic=old_result.get("topic") or board.title,
        language=board.language,
        status="ready" if report.passed and not unresolved else "needs_review",
        run_dir=str(run),
        video_path=str(video),
        thumbnail_path=str(thumb),
        title=seo.title,
        duration=vo.duration,
        seo=seo,
        quality=report,
        fact_check=fact_report,
    )
    _save(run / "result.json", result)
    return result


def default_redo(run_dir, edits=(), branding=None) -> PipelineResult:
    """Asli Gemini + Pixabay se (API ke background job ke liye)."""
    from app.services.gemini_client import GeminiClient
    try:
        gemini = GeminiClient()
    except Exception:  # noqa: BLE001 - key na ho to bhi render/resume chale
        gemini = None
    with httpx.Client(timeout=60) as http:
        return redo_run(run_dir, edits, http=http, gemini=gemini, branding=branding,
                        progress=lambda m: print(m, flush=True))
