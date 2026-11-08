"""Live test: long script ke scenes ke liye asli Pixabay clips + visual report + credits.
Usage: python -m scripts.try_long_clips [--scenes 15] [run folder]
Pehle 15 scenes (kam downloads). Poori 45 ke liye --scenes 45."""
import argparse
from pathlib import Path

import httpx

from app.services.long_clips import collect_long_clips
from app.services.long_script import LongScript
from app.services.long_visuals import credits_text, save_visuals

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("run", nargs="?", default=str(root / "output" / "long_test" / "how_black_holes_form_5min"))
ap.add_argument("--scenes", type=int, default=15)
a = ap.parse_args()
run = Path(a.run)
f = run / "long_script.json"
if not f.exists():
    raise SystemExit(f"[FAIL] {f} nahi mili. Pehle: python -m scripts.try_long_script ...")
board = LongScript.model_validate_json(f.read_text(encoding="utf-8")).storyboard
with httpx.Client(timeout=60) as http:
    clips, rep = collect_long_clips(board, http, run_dir=run, max_scenes=a.scenes)
land = sum(1 for c in clips if c.width >= c.height)
print(f"\nClips: {rep.total} | alag alag: {rep.unique} | landscape: {land}/{rep.total} | dobara lagi: {len(rep.reused_scenes)}")
for c in clips[:8]:
    print(f"  scene {c.scene_number:3}: {c.width}x{c.height} {c.duration:.0f}s  [{c.query}]  by {c.author or '?'}")
for w in rep.warnings:
    print("  [WARN]", w)
part = board.model_copy(update={"scenes": board.scenes[:a.scenes]})
vrep, credits = save_visuals(run, part, clips)
print("\nVisual report:", vrep.summary())
for w in vrep.warnings:
    print("  [VISUAL]", w)
print("Credits :", credits_text(credits))
print(f"Files   : {run / 'visual_report.json'}, {run / 'visual_credits.json'}")