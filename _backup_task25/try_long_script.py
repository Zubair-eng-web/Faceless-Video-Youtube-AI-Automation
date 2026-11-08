"""Live test: asli Gemini se long script. Free API calls lagti hain (outline + har chapter ki ek).
Usage: python -m scripts.try_long_script "How black holes form" --minutes 5 [--language English]
Dobara chalane par bane hue chapters dobara nahi likhe jate (resume)."""
import argparse
import re
from pathlib import Path

from app.services.long_script import LongConfig, generate_long_script, make_client

ap = argparse.ArgumentParser()
ap.add_argument("topic")
ap.add_argument("--minutes", type=float, default=5)
ap.add_argument("--language", default="English")
a = ap.parse_args()

root = Path(__file__).resolve().parent.parent
slug = re.sub(r"[^a-z0-9]+", "_", a.topic.lower()).strip("_")[:40] or "topic"
run_dir = root / "output" / "long_test" / f"{slug}_{int(a.minutes)}min"
cfg = LongConfig.from_env()
r = generate_long_script(a.topic, make_client(cfg), a.minutes, a.language, run_dir=run_dir, cfg=cfg)

b = r.storyboard
print(f"\nTitle   : {b.title}\nHook    : {b.hook}")
print(f"Minutes : {r.minutes:g} | Words: {r.words} (target ~{int(r.minutes * cfg.words_per_minute)}) | Scenes: {len(b.scenes)}")
for i, c in enumerate(r.chapters, 1):
    print(f"  {i:2}. {c.title}  [scenes {c.first_scene}-{c.last_scene}, {c.words} words]")
for w in r.warnings:
    print("  [WARN]", w)
queries = [s.search_query.lower() for s in b.scenes]
print(f"Unique search queries: {len(set(queries))}/{len(queries)}")
print(f"Folder  : {run_dir}")
