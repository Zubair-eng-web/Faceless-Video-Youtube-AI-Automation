"""Live test: published videos ke stats YouTube se lena (youtube.readonly permission chahiye)."""
from app.core import db, db_production
from app.core.analytics import summarize
from app.core.config import settings
from app.services.youtube_stats import refresh_stats


def main() -> None:
    db.init_db(settings.db_path)
    summary = refresh_stats(settings.db_path)
    print("Refresh:", summary)
    videos = db_production.published_videos(settings.db_path)
    if not videos:
        print("Abhi koi published video nahi.")
        return
    print("Summary:", summarize(videos))
    for v in videos:
        print(f"#{v['id']} {v['title']} | views {v['views']} | likes {v['likes']} | comments {v['comments']}")


if __name__ == "__main__":
    main()
