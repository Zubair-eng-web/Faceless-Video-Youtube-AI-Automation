import re
import sys
from pathlib import Path

count = sys.argv[1] if len(sys.argv) > 1 else "?"
r = Path(__file__).resolve().parent.parent / "README.md"
t = r.read_text(encoding="utf-8")
if "### Step 19" not in t:
    entry = f"""### Step 19: Script/clip edit aur dobara chalana
- `redo.py`: video ko uske run folder se dobara banata hai. Narration badli to voiceover, fact-check (sirf report, text khud nahi badalta) aur SEO dobara; query badli to sirf us scene ki clip. Pehle se bani `voiceover.json`, `clips.json`, `seo.json` dobara use hoti hain, sirf missing hissa banta hai, phir render, thumbnail aur quality check.
- Fail hui video ka run folder ab database mein save hota hai (`pipeline.LAST_RUN_DIR`), is liye wahin se resume ho sakti hai. Purani failed videos ka folder maujood nahi.
- API: `GET /videos/{{id}}/storyboard`, `POST /videos/{{id}}/redo` (statuses ready, needs_review, failed se). Dashboard video detail mein "Script/clips edit karein ya dobara banayen" panel.
- Render se pehle purani `video_core.mp4` hat jati hai, taake quality check purani video par na ho.
- Total {count} tests.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
t = re.sub(r"^\| Dashboard behtari \|[^\n]*\n", "", t, flags=re.M)
t = t.replace("| Trend research | Mukammal | 18 |",
              "| Trend research | Mukammal | 18 |\n| Script/clip edit, dobara chalana | Mukammal | 19 |")
s, e = t.find("**Agla step (Step 19)"), t.find("**Uske baad ke kaam:**")
if s != -1 and e != -1:
    t = t[:s] + ("**Agla step (Step 20): Deployment**: Windows Task Scheduler ya Docker mein chalana, "
                 "database ka backup, logs.\n\n") + t[e:]
t = re.sub(r"Step 18 par \d+ tests", f"Step 19 par {count} tests", t)
r.write_text(t, encoding="utf-8")
print("[OK] README mein Step 19 darj")
