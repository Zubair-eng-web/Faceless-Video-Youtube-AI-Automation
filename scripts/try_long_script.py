"""Live test: asli Gemini se long script (research + script + jaanch). Free API calls lagti hain
(1 research + 1 outline + har chapter ki ek).
Usage: python -m scripts.try_long_script "How black holes form" --minutes 5 [--language English] [--no-research]
Dobara chalane par bane hue outline/chapters/research dobara nahi bante (resume).
Purani script se naye research ke saath dobara banana ho to output/long_test ka folder delete kar dein."""
import argparse
import re
from pathlib import Path

from app.services.long_research import research_long
from app.services.long_script import LongConfig, generate_long_script, make_client
from app.services.long_validation import save_validation, validate_script

ap = argparse.ArgumentParser()
ap.add_argument("topic")
ap.add_argument("--minutes", type=float, default=5)
ap.add_argument("--language", default="English")
ap.add_argument("--no-research", action="store_true")
a = ap.parse_args()

root = Path(__file__).resolve().parent.parent
slug = re.sub(r"[^a-z0-9]+", "_", a.topic.lower()).strip("_")[:40] or "topic"
run_dir = root / "output" / "long_test" / f"{slug}_{int(a.minutes)}min"
cfg = LongConfig.from_env()
client = make_client(cfg)
researcher = None
holder = {}
if not a.no_research:
    def researcher(outline):
        holder["r"] = research_long(a.topic, outline, client, a.language, run_dir)
        return holder["r"]
r = generate_long_script(a.topic, client, a.minutes, a.language, run_dir=run_dir, cfg=cfg, researcher=researcher)

b = r.storyboard
print(f"\nTitle   : {b.title}\nHook    : {b.hook}")
print(f"Minutes : {r.minutes:g} | Words: {r.words} (target ~{int(r.minutes * cfg.words_per_minute)}) | Scenes: {len(b.scenes)}")
for i, c in enumerate(r.chapters, 1):
    print(f"  {i:2}. {c.title}  [scenes {c.first_scene}-{c.last_scene}, {c.words} words]")
for w in r.warnings:
    print("  [WARN]", w)
queries = [s.search_query.lower() for s in b.scenes]
print(f"Unique search queries: {len(set(queries))}/{len(queries)}")
if "r" in holder:
    print("Research:", holder["r"].summary())
    for w in holder["r"].warnings:
        print("  [RESEARCH]", w)
rep = validate_script(r, cfg)
save_validation(rep, run_dir)
print(f"Jaanch  : {'OK' if rep.ok else 'FAIL'} ({len(rep.errors)} errors, {len(rep.warnings)} warnings)")
for i in rep.issues:
    print(f"  [{i.level.upper()}] {i.message}")
print(f"Folder  : {run_dir}")