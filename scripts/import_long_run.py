"""Maujooda long run folder ko database mein import karna (dashboard par dikhane ke liye).
Usage: python -m scripts.import_long_run <run folder> [--channel ID]"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace as NS

from app.agents.seo_agent import SEOPack
from app.core import db
from app.core.config import settings
from app.services.long_quality import QAReport

ap = argparse.ArgumentParser()
ap.add_argument("run")
ap.add_argument("--channel", type=int, default=None)
a = ap.parse_args()
run = Path(a.run).resolve()
pkg = json.loads((run / "long_package.json").read_text(encoding="utf-8"))
qa = QAReport.model_validate_json((run / "long_quality.json").read_text(encoding="utf-8"))
video = run / "render" / "video.mp4"
script = json.loads((run / "long_script.json").read_text(encoding="utf-8"))
board = script["storyboard"]
topic, language = board.get("title", run.name), board.get("language", "English")

tags = " ".join(pkg["hashtags"])
desc = pkg["description"]
if tags and desc.endswith(tags):
    desc = desc[:-len(tags)].rstrip()
seo = SEOPack(title=pkg["title"], description=desc, hashtags=pkg["hashtags"], tags=pkg["tags"],
              thumbnail_text=pkg["thumbnail_text"])
db.init_db(settings.db_path)
vid = db.create_job(settings.db_path, a.channel, topic, language)
(run / "long_params.json").write_text(json.dumps(
    {"topic": topic, "language": language, "minutes": script.get("minutes", 10), "voice": None,
     "series_id": None, "episode": None}, ensure_ascii=False), encoding="utf-8")
status = "ready" if qa.ok else "needs_review"
res = NS(topic=topic, language=language, status=status, run_dir=str(run), video_path=str(video),
         thumbnail_path=str(Path(pkg["thumbnail_path"]).resolve()), title=pkg["title"],
         duration=float(qa.stats.get("duration") or 0), seo=seo, quality=qa)
db.transition(settings.db_path, vid, "generating", {"queued"})
db.finish_video(settings.db_path, vid, res)
print(f"Imported: video #{vid} ({status}). Dashboard refresh karein.")
