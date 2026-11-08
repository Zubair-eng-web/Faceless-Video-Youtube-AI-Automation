"""Live test: SEO (1 Gemini request) + thumbnail + quality check.
Pehle 'python -m scripts.try_video' chalayen taake video aur uska data maujood ho."""
import json
import sys

from app.agents.seo_agent import generate_seo
from app.core.config import settings
from app.core.models import Storyboard
from app.services.gemini_client import GeminiClient, GeminiError
from app.services.pixabay import SceneClip
from app.services.quality import check_video
from app.services.thumbnail import ThumbnailError, extract_frame, make_thumbnail
from app.services.tts import Voiceover


def main() -> None:
    settings.ensure_dirs()
    out_dir = settings.output_dir / "video_test"
    story_file = settings.output_dir / "last_storyboard.json"
    needed = [out_dir / "video.mp4", out_dir / "voiceover.json", out_dir / "clips.json",
              out_dir / "captions.ass", story_file]
    missing = [p.name for p in needed if not p.exists()]
    if missing:
        print("Ye files nahi mili:", ", ".join(missing))
        print("Patch ke baad 'python -m scripts.try_video' dobara chalayen.")
        sys.exit(1)

    board = Storyboard.model_validate_json(story_file.read_text(encoding="utf-8"))
    vo = Voiceover.model_validate_json((out_dir / "voiceover.json").read_text(encoding="utf-8"))
    clips = [SceneClip.model_validate(c) for c in json.loads((out_dir / "clips.json").read_text(encoding="utf-8"))]

    print("1/3 SEO ban raha hai (1 Gemini request)...")
    try:
        seo = generate_seo(board, GeminiClient())
    except (GeminiError, ValueError) as exc:
        print("SEO error:", exc)
        sys.exit(1)
    (out_dir / "seo.json").write_text(seo.model_dump_json(indent=2), encoding="utf-8")

    print("2/3 Thumbnail ban raha hai...")
    try:
        frame = extract_frame(out_dir / "segments" / "seg_01.mp4", 1.0, out_dir / "thumb_frame.jpg")
        thumb = make_thumbnail(frame, seo.thumbnail_text, out_dir / "thumbnail.jpg",
                               font_path=settings.fonts_dir / "arialbd.ttf")
    except ThumbnailError as exc:
        print("Thumbnail error:", exc)
        sys.exit(1)

    print("3/3 Quality check chal raha hai...")
    report = check_video(out_dir / "video.mp4", vo, board, clips, out_dir / "captions.ass")
    (out_dir / "quality.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print()
    print("TITLE      :", seo.title, f"({len(seo.title)} chars)")
    print("HASHTAGS   :", " ".join(seo.hashtags))
    print("TAGS       :", ", ".join(seo.tags))
    print("THUMB TEXT :", seo.thumbnail_text)
    print("DESCRIPTION:")
    print(seo.full_description)
    print()
    print("Thumbnail  :", thumb, f"({thumb.stat().st_size / 1000:.0f} KB)")
    print("Stats      :", report.stats)
    for issue in report.issues:
        print(f"  [{issue.level.upper()}] {issue.code}: {issue.message}")
    print("QUALITY    :", "PASS" if report.passed else "FAIL",
          f"({len(report.errors)} errors, {len(report.warnings)} warnings)")


if __name__ == "__main__":
    main()
