"""Poori pipeline: topic -> script -> voiceover -> clips -> video -> SEO -> thumbnail -> quality check."""
import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from app.agents.script_agent import generate_script
from app.agents.seo_agent import SEOPack, generate_seo
from app.core.config import settings
from app.services.pixabay import collect_clips
from app.services.quality import QualityReport, check_video
from app.services.thumbnail import extract_frame, make_thumbnail
from app.services.tts import apply_durations, generate_voiceover
from app.services.video_editor import render_video
from app.services.fact_check import FactCheckReport, run_fact_check

TOTAL_STEPS = 7
LAST_RUN_DIR = None  # aakhri run ka folder (fail hui job ka folder yaad rakhne ke liye)


class PipelineError(RuntimeError):
    def __init__(self, step: str, message: str):
        super().__init__(f"[{step}] {message}")
        self.step = step


class PipelineResult(BaseModel):
    topic: str
    language: str
    status: str  # "ready" ya "needs_review"
    run_dir: str
    video_path: str
    thumbnail_path: str
    title: str
    duration: float
    seo: SEOPack
    quality: QualityReport
    fact_check: FactCheckReport | None = None


def core_video(run_dir, video):
    """Intro/outro lagi ho to quality check asli content wali video (video_core.mp4) par."""
    core = Path(run_dir) / "video_core.mp4"
    return core if core.exists() else video


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:max_len].strip("_")
    return slug or "video"


def _step(name: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(name, str(exc)) from exc


def _save(path: Path, model) -> None:
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def run_pipeline(
    topic: str,
    gemini,
    http,
    language: str = "English",
    target_seconds: int = 40,
    voice: str | None = None,
    out_root=None,
    progress=print,
    now=datetime.now,
    script_fn=generate_script,
    voiceover_fn=generate_voiceover,
    clips_fn=collect_clips,
    render_fn=render_video,
    seo_fn=generate_seo,
    frame_fn=extract_frame,
    thumb_fn=make_thumbnail,
    check_fn=check_video,
    fact_fn=run_fact_check,
    branding=None,
) -> PipelineResult:
    topic = " ".join(topic.split())
    if not topic:
        raise ValueError("Topic khali hai")

    root = Path(out_root) if out_root else settings.output_dir / "runs"
    run_dir = root / f"{now():%Y%m%d_%H%M%S}_{slugify(topic)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    global LAST_RUN_DIR
    LAST_RUN_DIR = str(run_dir)

    progress(f"[1/{TOTAL_STEPS}] Script aur storyboard...")
    board = _step("script", script_fn, topic, gemini, language=language, target_seconds=target_seconds)
    _save(run_dir / "storyboard.json", board)

    progress("    Fact-check...")
    board, fact_report = fact_fn(board, gemini)
    _save(run_dir / "fact_check.json", fact_report)
    progress("    " + fact_report.summary())
    if fact_report.fixed_scenes:
        _save(run_dir / "storyboard.json", board)

    progress(f"[2/{TOTAL_STEPS}] Voiceover...")
    vo = _step("voiceover", voiceover_fn, board, run_dir / "audio", voice=voice)
    _save(run_dir / "voiceover.json", vo)

    progress(f"[3/{TOTAL_STEPS}] Stock clips...")
    timed_board = apply_durations(board, vo)  # clips voiceover ki asli durations se chuni jayen
    clips = _step("clips", clips_fn, timed_board, http)
    (run_dir / "clips.json").write_text("[" + ",".join(c.model_dump_json() for c in clips) + "]", encoding="utf-8")

    progress(f"[4/{TOTAL_STEPS}] Video render (1-2 minute)...")
    video = _step("render", render_fn, board, clips, vo, run_dir,
                 **({"branding": branding} if branding else {}))

    progress(f"[5/{TOTAL_STEPS}] SEO...")
    seo = _step("seo", seo_fn, board, gemini)
    _save(run_dir / "seo.json", seo)

    progress(f"[6/{TOTAL_STEPS}] Thumbnail...")
    frame = _step("thumbnail", frame_fn, run_dir / "segments" / "seg_01.mp4", 1.0, run_dir / "thumb_frame.jpg")
    thumb = _step("thumbnail", thumb_fn, frame, seo.thumbnail_text, run_dir / "thumbnail.jpg",
                  font_path=settings.fonts_dir / "arialbd.ttf")

    progress(f"[7/{TOTAL_STEPS}] Quality check...")
    report = _step("quality", check_fn, core_video(run_dir, video), vo, board, clips, run_dir / "captions.ass")
    _save(run_dir / "quality.json", report)

    result = PipelineResult(
        topic=topic,
        language=language,
        status="ready" if report.passed and not fact_report.unresolved_wrong else "needs_review",
        run_dir=str(run_dir),
        video_path=str(video),
        thumbnail_path=str(thumb),
        title=seo.title,
        duration=vo.duration,
        seo=seo,
        quality=report,
        fact_check=fact_report,
    )
    _save(run_dir / "result.json", result)
    return result
