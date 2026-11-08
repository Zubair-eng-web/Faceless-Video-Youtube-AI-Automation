"""Long-form pipeline: stages, progress file, resume, result adapter."""
import json
import time
from pathlib import Path
from types import SimpleNamespace as NS

PROGRESS_FILE = "long_progress.json"


def read_progress(run) -> dict:
    f = Path(run) / PROGRESS_FILE
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except (OSError, ValueError):
        return {}


def write_progress(run, **kw) -> dict:
    run = Path(run)
    run.mkdir(parents=True, exist_ok=True)
    data = read_progress(run)
    data.update(kw)
    data["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (run / PROGRESS_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _save_script(c):
    (Path(c.run) / "long_script.json").write_text(c.script.model_dump_json(indent=2), encoding="utf-8")


def st_script(c):
    from app.services.long_research import research_long
    from app.services.long_script import LongScript, generate_long_script
    f = Path(c.run) / "long_script.json"
    if f.is_file():
        c.script = LongScript.model_validate_json(f.read_text(encoding="utf-8"))
        return
    c.script = generate_long_script(
        c.topic, c.client, minutes=c.minutes, language=c.language, style=c.style, run_dir=c.run, progress=c.log,
        researcher=lambda o: research_long(c.topic, o, c.client, language=c.language, run_dir=c.run, progress=c.log))
    _save_script(c)


def st_validate(c):
    from app.services.long_validation import save_validation, validate_script
    rep = validate_script(c.script)
    save_validation(rep, c.run)
    if rep.errors:
        c.log(f"Script jaanch: {len(rep.errors)} error (long_validation.json dekhein)")


def st_factcheck(c):
    from app.services.long_factcheck import fact_check_long
    from app.services.long_script import LongScript
    res = fact_check_long(c.script, c.client, run_dir=c.run, progress=c.log)
    items = res if isinstance(res, tuple) else (res,)
    for x in items:
        if isinstance(x, LongScript):
            c.script = x
            _save_script(c)
        elif hasattr(x, "needs_review"):
            v = x.needs_review
            c.needs_review = bool(v() if callable(v) else v)


def st_narration(c):
    from app.services.long_narration import NarrationConfig, generate_long_voiceover
    cfg = NarrationConfig.from_env()
    if c.voice:
        cfg.voice = c.voice
    c.vo, _ = generate_long_voiceover(c.script, Path(c.run) / "narration", cfg=cfg, progress=c.log)


def st_clips(c):
    from app.services.long_clips import collect_long_clips
    from app.services.long_visuals import save_visuals
    c.clips, _ = collect_long_clips(c.script.storyboard, c.http, run_dir=c.run, progress=c.log)
    save_visuals(c.run, c.script.storyboard, c.clips)


def st_render(c):
    from app.services.long_render import render_long_video
    board = c.script.storyboard
    ends = [i for i, s in enumerate(board.scenes[:-1], start=1)
            if any(ch.last_scene == s.number for ch in c.script.chapters)]
    c.video = render_long_video(board, c.clips, c.vo, Path(c.run) / "render", chapter_ends=ends,
                                transition=c.transition, progress=c.log)


def st_quality(c):
    from app.services.long_quality import check_long_quality, load_long_run
    c.script, board, clips, vo = load_long_run(c.run, 0)
    c.qa = check_long_quality(c.script, board, clips, vo, c.run, c.video)


def st_package(c):
    from app.services.long_package import build_long_package
    script, board, clips, vo = _reload(c)
    c.pkg = build_long_package(script, board, clips, vo, c.run, c.video, client=c.client, progress=c.log)


def _reload(c):
    from app.services.long_quality import load_long_run
    return load_long_run(c.run, 0)


STAGES = [("script", st_script), ("validate", st_validate), ("factcheck", st_factcheck),
          ("narration", st_narration), ("clips", st_clips), ("render", st_render),
          ("quality", st_quality), ("package", st_package)]


def run_stages(c, stages=None):
    stages = stages or STAGES
    write_progress(c.run, status="running", error=None)
    for i, (name, fn) in enumerate(stages):
        write_progress(c.run, stage=name, pct=int(100 * i / len(stages)), status="running")
        try:
            fn(c)
        except Exception as exc:
            write_progress(c.run, status="failed", stage=name, error=str(exc) or type(exc).__name__)
            raise
    write_progress(c.run, status="done", stage="done", pct=100)
    return c


def to_result(c):
    """db.finish_video aur publisher ke liye PipelineResult jaisa object."""
    from app.agents.seo_agent import SEOPack
    pkg, qa = c.pkg, c.qa
    tag_line = " ".join(pkg.hashtags)
    desc = pkg.description
    if tag_line and desc.endswith(tag_line):
        desc = desc[:-len(tag_line)].rstrip()
    seo = SEOPack(title=pkg.title, description=desc, hashtags=pkg.hashtags, tags=pkg.tags,
                  thumbnail_text=pkg.thumbnail_text)
    status = "ready" if qa.ok and not getattr(c, "needs_review", False) else "needs_review"
    return NS(topic=c.topic, language=c.language, status=status, run_dir=str(c.run), video_path=str(c.video),
              thumbnail_path=pkg.thumbnail_path, title=pkg.title,
              duration=float(qa.stats.get("duration") or 0.0), seo=seo, quality=qa)


def run_long_pipeline(topic, language, minutes, run_dir, client, http, voice=None, style=None,
                      transition=0.4, log=print):
    run = Path(run_dir)

    def say(m):
        write_progress(run, message=str(m)[-200:])
        log(m)

    c = NS(topic=topic, language=language, minutes=minutes, run=run, client=client, http=http, voice=voice,
           style=style, transition=transition, log=say, needs_review=False)
    run_stages(c)
    return to_result(c)


def default_long_runner(topic, language, minutes, voice, run_dir, style=None, transition=0.4):
    import httpx
    from app.services.long_script import make_client
    with httpx.Client(timeout=60) as http:
        return run_long_pipeline(topic, language, minutes, run_dir, make_client(), http, voice=voice,
                                 style=style, transition=transition, log=lambda m: print(m, flush=True))
