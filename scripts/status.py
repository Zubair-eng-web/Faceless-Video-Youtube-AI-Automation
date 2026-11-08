"""Project ka haal: keys, channels, schedule, videos, YouTube permissions."""
from app.core import db
from app.core.config import settings
from app.services.youtube_stats import token_scopes


def main() -> None:
    p = settings.db_path
    db.init_db(p)
    print("Missing keys :", ", ".join(settings.missing_keys()) or "koi nahi")
    print("AUTO_PRODUCE :", settings.auto_produce, "| AUTO_PUBLISH:", settings.auto_publish)
    with db.connect(p) as con:
        rows = con.execute("SELECT status, COUNT(*) AS n FROM videos GROUP BY status").fetchall()
    print("Videos       :", {r["status"]: r["n"] for r in rows} or "abhi koi nahi")
    for ch in db.list_channels(p):
        scopes = token_scopes(ch["id"])
        print(f"\nChannel #{ch['id']} {ch['name']} | niche: {ch['niche'] or '-'} | {ch['language']}")
        print(f"  schedule  : roz {ch['daily_videos']} videos, {ch['produce_at']} ke baad, {ch['video_seconds']}s")
        print(f"  YouTube   : {'connected' if scopes else 'connect nahi'}"
              f"{'' if not scopes or any(s.endswith('readonly') for s in scopes) else ' (readonly permission nahi)'}")


if __name__ == "__main__":
    main()
