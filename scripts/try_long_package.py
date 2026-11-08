"""Live test: long-form YouTube package. Usage: python -m scripts.try_long_package [--scenes 10] [--force] [run folder]
1 Gemini request lagti hai (dobara chalane par cache)."""
import argparse
from pathlib import Path

from app.services.long_package import build_long_package
from app.services.long_quality import load_long_run
from app.services.long_script import make_client

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("run", nargs="?", default=str(root / "output" / "long_test" / "how_black_holes_form_5min"))
ap.add_argument("--scenes", type=int, default=10)
ap.add_argument("--force", action="store_true")
a = ap.parse_args()
run = Path(a.run)
try:
    script, board, clips, vo = load_long_run(run, a.scenes)
except FileNotFoundError as e:
    raise SystemExit(f"[FAIL] {e}")
pkg = build_long_package(script, board, clips, vo, run, run / "render" / "video.mp4",
                         client=make_client(), force=a.force)
print("\nTitle     :", pkg.title)
print("Hashtags  :", " ".join(pkg.hashtags))
print("Tags      :", len(pkg.tags), pkg.tags[:6])
print("Thumbnail :", pkg.thumbnail_path, f"[{pkg.thumbnail_text}]")
print("Chapters  :", [f"{c['time']} {c['title']}" for c in pkg.chapters] or "-")
print("Metadata  :", pkg.metadata)
for w in pkg.warnings:
    print("  [WARN]", w)
print("\n--- Description ---\n" + pkg.description)
print("\nReport    :", run / "long_package.json")
