"""Live test: sab se nayi video YouTube par upload (default PRIVATE). Ek upload = 1600 quota units."""
import argparse
import sys

from app.core.config import settings
from app.pipeline import PipelineResult
from app.services.youtube import YouTubeError, upload_to_youtube


def latest_result():
    files = sorted((settings.output_dir / "runs").glob("*/result.json"), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    return PipelineResult.model_validate_json(files[-1].read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", type=int, default=1, help="database me channel ki id")
    parser.add_argument("--privacy", choices=["private", "unlisted"], default="private")
    args = parser.parse_args()

    result = latest_result()
    if result is None:
        print("Koi video nahi mili. Pehle 'python -m scripts.make_video \"topic\"' chalayen.")
        sys.exit(1)
    print("Video  :", result.title)
    print("File   :", result.video_path)
    print("Privacy:", args.privacy, "| Channel id:", args.channel)
    if input("YouTube par upload karein? (y/n): ").strip().lower() != "y":
        print("Cancel.")
        return

    try:
        outcome = upload_to_youtube(
            args.channel, result.video_path, result.seo.title, result.seo.full_description,
            result.seo.tags, thumbnail_path=result.thumbnail_path, privacy=args.privacy,
            progress=lambda p: print(f"  upload {p * 100:.0f}%", end="\r"),
        )
    except (YouTubeError, ValueError) as exc:
        print()
        print("Error:", exc)
        sys.exit(1)

    video_id = outcome["video_id"]
    print()
    print("Upload ho gayi. Video id:", video_id)
    print("Studio :", f"https://studio.youtube.com/video/{video_id}/edit")
    print("Link   :", f"https://www.youtube.com/watch?v={video_id}")
    if outcome["thumbnail_error"]:
        print("Thumbnail nahi lagi:", outcome["thumbnail_error"])
    else:
        print("Thumbnail lag gayi.")


if __name__ == "__main__":
    main()
