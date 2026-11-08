from app.core import db, db_production
from app.core.config import settings
from datetime import datetime

p = settings.db_path
db.init_db(p)
for ch in db.list_channels(p):
    row = db_production.set_channel_schedule(p, ch["id"], 3, "00:00", 40)
    today = datetime.now().date().isoformat()
    print("Schedule set:", row["name"], row["daily_videos"], row["produce_at"],
          "| aaj (bani, fail):", db_production.count_today(p, ch["id"], today))
for v in db.list_videos(p) if hasattr(db, "list_videos") else []:
    print("Video", v["id"], v["status"], v.get("error") or "")
