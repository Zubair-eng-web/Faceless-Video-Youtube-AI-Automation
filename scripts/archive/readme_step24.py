import re
import sys
from pathlib import Path

count = sys.argv[1] if len(sys.argv) > 1 else "?"
r = Path(__file__).resolve().parent.parent / "README.md"
t = r.read_text(encoding="utf-8")
if "### Step 24" not in t:
    entry = f"""### Step 24: Long-form chapter-wise fact-check
- `long_factcheck.py`: har chapter alag Google Search grounding ke saath jaancha jata hai (1 call, kabhi kabhi 1 aur structuring ki). Grounding fail ho to baqi chapters Gemini ke knowledge se, report mein saaf likha aur video `needs_review`. Sirf pakka ghalat dawa theek hota hai (lambai ke andar), shak wale dawe sirf warning.
- Resume: `long_fact_NN.json`. Output `fact_check.json` (purane dashboard ke format mein), `long_fact_check.json` (sources ke saath), `storyboard.json` (fixes ke baad).
- Settings: `LONG_FACTCHECK_GROUNDED` (default 1), `LONG_FACTCHECK_AUTOFIX` (default 1).
- Live test: `scripts/try_long_factcheck.py`. Total {count} tests.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
t = re.sub(r"Halat: Step \d+ tak mukammal", "Halat: Step 24 tak mukammal", t)
r.write_text(t, encoding="utf-8")
print("[OK] README mein Step 24 darj")
