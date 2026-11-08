"""Live test: long script ka chapter-wise fact-check (asli Gemini + Google Search).
Usage: python -m scripts.try_long_factcheck [run folder]   (default: output/long_test/how_black_holes_form_5min)
Dobara chalane par jaanche hue chapters dobara nahi jaanche jate. Auto-fix chalta hai, storyboard.json update hota hai."""
import sys
from pathlib import Path

from app.services.long_factcheck import fact_check_long
from app.services.long_script import LongScript, make_client

root = Path(__file__).resolve().parent.parent
run = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "output" / "long_test" / "how_black_holes_form_5min"
f = run / "long_script.json"
if not f.exists():
    raise SystemExit(f"[FAIL] {f} nahi mili. Pehle: python -m scripts.try_long_script ...")
script = LongScript.model_validate_json(f.read_text(encoding="utf-8"))
board, rep = fact_check_long(script, make_client(), run_dir=run)

print("\n" + rep.summary())
for c in rep.chapters:
    print(f"  Chapter {c.index} {c.title}: {'web' if c.grounded else 'knowledge'}, {len(c.claims)} daway, fixes: {sorted(c.fixes)}")
    for k in c.claims:
        if k.verdict != "ok":
            print(f"     [{k.verdict}] scene {k.scene_number}: {k.claim} -> {k.reason}")
for w in rep.warnings:
    print("  [WARN]", w)
for s in rep.sources[:8]:
    print("  source:", s)
print("Needs review:", rep.needs_review)
