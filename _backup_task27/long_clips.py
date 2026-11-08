"""Long-form clips: landscape ko tarjih, repeat kam, resume, rate-limit ka waqfa.

Har clip ek hi dafa; jab sab options khatam hon to sabse purani use hui clip dobara (report mein darj).
"""
import time
from pathlib import Path

from pydantic import BaseModel, Field

from app.services import pixabay as px
from app.services.pixabay import PixabayError, SceneClip

PER_PAGE = 30


class ClipReport(BaseModel):
    total: int = 0
    unique: int = 0
    reused_scenes: list[int] = Field(default_factory=list)
    reused_from_resume: int = 0
    warnings: list[str] = Field(default_factory=list)


def score_long(c, needed: float) -> float:
    s = 100.0 if c.width >= c.height else 0.0
    s += 20 if c.duration >= needed else -(needed - c.duration) * 2
    if min(c.width, c.height) >= px.TARGET_SHORT_SIDE:
        s += 10
    return s


def pick_long(candidates, needed: float, used) -> object | None:
    pool = [c for c in candidates if c.id not in used]
    return max(pool, key=lambda c: score_long(c, needed)) if pool else None


def long_query_options(scene, title: str) -> list[str]:
    q = " ".join(scene.search_query.split())
    vis = " ".join(scene.visual_description.split()[:4])
    out = []
    for cand in (q, " ".join(q.split()[:2]), vis, title):
        cand = " ".join(cand.split())
        if cand and cand not in out:
            out.append(cand)
    return out


def _load(path):
    try:
        import json
        return {c["scene_number"]: SceneClip.model_validate(c)
                for c in json.loads(Path(path).read_text(encoding="utf-8"))}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def _save(path, clips):
    Path(path).write_text("[" + ",".join(c.model_dump_json() for c in clips) + "]", encoding="utf-8")


def collect_long_clips(board, client, api_key=None, cache_dir=None, run_dir=None, max_scenes=None,
                       progress=print, search_fn=px.search_videos, download_fn=px.download_clip,
                       sleep=time.sleep, throttle: float = 0.65):
    """(clips, ClipReport). Fail sirf tab jab ek bhi clip na mile."""
    out_file = Path(run_dir) / "clips.json" if run_dir else None
    saved = _load(out_file) if out_file else {}
    report = ClipReport()
    used: set[int] = set()
    last_use: dict[int, int] = {}
    result: list[SceneClip] = []
    scenes = board.scenes[:max_scenes]

    for i, scene in enumerate(scenes, 1):
        prior = saved.get(scene.number)
        if prior and Path(prior.path).exists():
            result.append(prior)
            used.add(prior.clip_id)
            last_use[prior.clip_id] = scene.number
            report.reused_from_resume += 1
            continue

        chosen, used_query, errors = None, "", 0
        for q in long_query_options(scene, board.title):
            sleep(throttle)
            try:
                cands = search_fn(q, client, api_key=api_key, cache_dir=cache_dir, per_page=PER_PAGE, sleep=sleep)
            except Exception:  # noqa: BLE001 - ek query fail ho to agli
                errors += 1
                continue
            chosen = pick_long(cands, scene.duration, used)
            if chosen:
                used_query = q
                break

        if chosen:
            path = download_fn(chosen, client, cache_dir=cache_dir, sleep=sleep)
            used.add(chosen.id)
            last_use[chosen.id] = scene.number
            clip = SceneClip(scene_number=scene.number, clip_id=chosen.id, path=str(path), query=used_query,
                             width=chosen.width, height=chosen.height, duration=chosen.duration,
                             portrait=chosen.is_portrait, page_url=chosen.page_url)
        elif result:
            oldest = min(result, key=lambda c: last_use.get(c.clip_id, 0))
            last_use[oldest.clip_id] = scene.number
            clip = oldest.model_copy(update={"scene_number": scene.number})
            report.reused_scenes.append(scene.number)
            if errors:
                report.warnings.append(f"Scene {scene.number}: {errors} search fail hui, purani clip dobara lagi")
        else:
            raise PixabayError(f"Scene {scene.number} ke liye koi clip nahi mila ('{scene.search_query}')")

        result.append(clip)
        if out_file and i % 10 == 0:
            _save(out_file, result)
            progress(f"Clips {i}/{len(scenes)}")

    if out_file:
        _save(out_file, result)
    report.total = len(result)
    report.unique = len({c.clip_id for c in result})
    if report.reused_scenes:
        report.warnings.append(f"{len(report.reused_scenes)} scenes mein clip dobara lagi (nayi clip nahi mili)")
    return result, report
