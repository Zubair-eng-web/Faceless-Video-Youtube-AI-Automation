"""Live test: output/last_storyboard.json ka asli Gemini se fact-check (auto-fix band, sirf report)."""
import sys
from pathlib import Path

from app.core.models import Storyboard
from app.services.fact_check import run_fact_check
from app.services.gemini_client import GeminiClient

p = Path(__file__).resolve().parent.parent / "output" / "last_storyboard.json"
if not p.exists():
    print("[FAIL] output/last_storyboard.json nahi mili. Pehle: python -m scripts.try_script")
    sys.exit(1)

board = Storyboard.model_validate_json(p.read_text(encoding="utf-8"))
_, report = run_fact_check(board, GeminiClient(), auto_fix=False)
print(report.summary())
for c in report.claims:
    print(f"  [{c.verdict:8}] scene {c.scene_number}: {c.claim}" + (f"  -> {c.reason}" if c.reason else ""))
sys.exit(0 if report.checked else 1)
