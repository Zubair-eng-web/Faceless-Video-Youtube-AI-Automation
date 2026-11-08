"""Topic se poori video: python -m scripts.make_video "topic"  ya  --niche "niche"."""
import argparse
import sys

import httpx

from app.agents.research_agent import suggest_topics
from app.core.config import settings
from app.pipeline import PipelineError, run_pipeline
from app.services.gemini_client import GeminiClient, GeminiError


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Hindi/Urdu text console me sahi dikhe
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Topic se poori video banayein")
    parser.add_argument("topic", nargs="?", help="Video ka topic")
    parser.add_argument("--niche", help="Topic na do to is niche se Gemini topic chunega")
    parser.add_argument("--language", default="English")
    parser.add_argument("--seconds", type=int, default=40)
    parser.add_argument("--voice", default=None)
    args = parser.parse_args()
    if not args.topic and not args.niche:
        parser.error("Topic ya --niche me se ek zaroor dein")

    settings.ensure_dirs()
    missing = settings.missing_keys()
    if missing:
        print("Ye keys .env me nahi hain:", ", ".join(missing))
        sys.exit(1)

    try:
        gemini = GeminiClient()
        topic = args.topic
        if not topic:
            topics = suggest_topics(args.niche, gemini, count=3, language=args.language)
            if not topics:
                print("Koi topic nahi aaya.")
                sys.exit(1)
            topic = topics[0].title
            print("Topic chuna gaya:", topic)
        with httpx.Client(timeout=60) as http:
            result = run_pipeline(topic, gemini, http, language=args.language,
                                  target_seconds=args.seconds, voice=args.voice)
    except (GeminiError, PipelineError, ValueError) as exc:
        print("Error:", exc)
        sys.exit(1)

    print()
    print("STATUS   :", result.status.upper())
    print("TITLE    :", result.title)
    print(f"DURATION : {result.duration:.1f}s")
    print("VIDEO    :", result.video_path)
    print("THUMBNAIL:", result.thumbnail_path)
    print("FOLDER   :", result.run_dir)
    for issue in result.quality.issues:
        print(f"  [{issue.level.upper()}] {issue.code}: {issue.message}")
    sys.exit(0 if result.status == "ready" else 2)


if __name__ == "__main__":
    main()
