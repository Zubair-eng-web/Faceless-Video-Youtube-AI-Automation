"""Live test: long-form quality check. Usage: python -m scripts.try_long_quality [--scenes 10] [--skip-black] [run folder]"""
import argparse
import sys
from pathlib import Path

from app.services.long_quality import check_long_quality, load_long_run

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("run", nargs="?", default=str(root / "output" / "long_test" / "how_black_holes_form_5min"))
ap.add_argument("--scenes", type=int, default=10)
ap.add_argument("--skip-black", action="store_true")
a = ap.parse_args()
run = Path(a.run)
try:
    script, board, clips, vo = load_long_run(run, a.scenes)
except FileNotFoundError as e:
    raise SystemExit(f"[FAIL] {e}")
rep = check_long_quality(script, board, clips, vo, run, run / "render" / "video.mp4", skip_black=a.skip_black)
print("\nQuality:", rep.summary())
print("Stats  :", rep.stats)
for i in rep.issues:
    where = f" scene {i.scene}" if i.scene else ""
    print(f"  [{i.level.upper()}] {i.area}{where}: {i.msg}" + (f"  -> {i.fix}" if i.fix else ""))
print("Report :", run / "long_quality.json")
sys.exit(0 if rep.ok else 1)
