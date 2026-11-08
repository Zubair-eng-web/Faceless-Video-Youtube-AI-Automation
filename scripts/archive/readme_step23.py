import re
import sys
from pathlib import Path

count = sys.argv[1] if len(sys.argv) > 1 else "?"
r = Path(__file__).resolve().parent.parent / "README.md"
t = r.read_text(encoding="utf-8")
if "### Step 23" not in t:
    entry = f"""### Step 23: Long-form script (outline, chapters, scenes)
- `long_script.py`: pehle outline, phir chapter by chapter script (har chapter ki alag Gemini call, pichle chapter ka akhri hissa aur poora outline context mein). Lafzon ki ginti jaanchi jati hai, galat ho to ek dafa dobara. Lambi narration jumlon par scenes mein tooti hai, search query hamesha English mein. Output ek `Storyboard` hai, to purani pipeline ke models wahi rehte hain. Series ke liye `SeriesStyle` (narrator, tone, audience, episode).
- Resume: `long_outline.json` aur `long_chapter_NN.json` run folder mein, dobara chalane par bane hue chapters dobara nahi likhe jate.
- Settings sirf environment variables se: `LONG_WORDS_PER_MINUTE`, `LONG_SCENE_SECONDS`, `LONG_MAX_SCENE_WORDS`, `LONG_MIN_MINUTES`, `LONG_MAX_MINUTES`, `LONG_MAX_SCENES`, `LONG_GEMINI_MODEL`.
- Live test: `scripts/try_long_script.py`. Shorts mode ko haath nahi lagaya. Total {count} tests.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
t = re.sub(r"Halat: Step \d+ tak mukammal", "Halat: Step 23 tak mukammal", t)
r.write_text(t, encoding="utf-8")
print("[OK] README mein Step 23 darj")
