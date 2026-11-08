from app.core import db, db_production
from app.core.config import settings
for ch in db.list_channels(settings.db_path):
    row = db_production.set_channel_schedule(settings.db_path, ch["id"], 1, "09:00", 40)
    print("Schedule:", row["name"], "roz", row["daily_videos"], "video,", row["produce_at"], "ke baad")
