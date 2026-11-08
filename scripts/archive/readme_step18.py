import re
import sys
from pathlib import Path

count = sys.argv[1] if len(sys.argv) > 1 else "?"
r = Path(__file__).resolve().parent.parent / "README.md"
t = r.read_text(encoding="utf-8")
if "### Step 18" not in t:
    entry = f"""### Step 18: Trend research
- `trends.py`: YouTube Data API (`chart=mostPopular`, 1 quota unit) se trending titles. Niche se category (maslan space/science, gaming) aur language se region (Urdu PK, Hindi IN, English US; `TRENDS_REGION` se badal sakte hain). Category se kuch na mile to general most popular.
- `research_agent.suggest_topics` ko `trends` parameter, Gemini ko titles sirf inspiration ke liye. `runner.py` khud trends laata hai, to dashboard aur auto production dono mein topic trending data se chunta hai.
- Token na ho, quota khatam ho ya kuch fail ho to purana research chalta hai, video nahi rukti.
- Live test: `scripts/try_trends.py`. Total {count} tests.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
t = re.sub(r"^\| (Behtar trend research|Channel branding) \| (YouTube ya Google|Har channel)[^\n]*\n", "", t, flags=re.M)
t = t.replace("| Trend research, branding | Baqi | Roadmap |",
              "| Channel branding | Mukammal | 17 |\n| Trend research | Mukammal | 18 |")
s, e = t.find("**Agla step (Step 18)"), t.find("**Uske baad ke kaam:**")
if s != -1 and e != -1:
    t = t[:s] + ("**Agla step (Step 19): Dashboard behtari**: render se pehle script edit karna, "
                 "kisi scene ki clip badalna, fail hue step se dobara chalana.\n\n") + t[e:]
t = re.sub(r"Step 17 par \d+ tests", f"Step 18 par {count} tests", t)
r.write_text(t, encoding="utf-8")
print("[OK] README mein Step 18 darj")
