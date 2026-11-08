"""Maintenance: log rotation + database backup + purane run folders ki list.
Usage: python -m scripts.maintenance [--days 14] [--keep 7] [--delete-runs]
Bina --delete-runs ke kuch delete nahi hota, sirf list aur size dikhta hai."""
import argparse
from pathlib import Path

from app.core import db
from app.core.config import settings
from app.services.maintenance import backup_db, delete_runs, find_deletable_runs, rotate_logs

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--days", type=float, default=14)
ap.add_argument("--keep", type=int, default=7)
ap.add_argument("--delete-runs", action="store_true")
a = ap.parse_args()
if a.days < 1:
    raise SystemExit("--days kam az kam 1 hona chahiye (chalti jobs ke folder bachane ke liye)")

rotated = rotate_logs(root / "logs")
print("Logs rotate:", ", ".join(rotated) if rotated else "zaroorat nahi")

videos = []
if settings.db_path.exists():
    dest = backup_db(settings.db_path, keep=a.keep)
    print(f"Backup: {dest}")
    videos = db.list_videos(settings.db_path, None, None, 100000)
else:
    print("Database abhi nahi bana, backup chhor diya")

items = find_deletable_runs(settings.output_dir / "runs", videos, a.days)
mb = sum(i["bytes"] for i in items) / 1024 / 1024
print(f"{a.days:g} din se purane rejected/failed/orphan run folders: {len(items)} ({mb:.1f} MB)")
for i in items:
    print(f"  [{i['status']}] {i['path'].name}")
if items and a.delete_runs:
    print(f"{delete_runs(items)} folder delete hue")
elif items:
    print("Delete karne ke liye: python -m scripts.maintenance --delete-runs")
