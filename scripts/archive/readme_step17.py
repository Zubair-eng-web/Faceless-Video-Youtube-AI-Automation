import sys
from pathlib import Path

count = sys.argv[1] if len(sys.argv) > 1 else "?"
r = Path(__file__).resolve().parent.parent / "README.md"
t = r.read_text(encoding="utf-8")
if "### Step 17" not in t:
    entry = f"""### Step 17: Channel branding
- `branding.py`: har channel ke captions ka highlight/text rang aur size, logo watermark (jagah, opacity, chaurai), intro/outro. Settings channel ke `branding_json` column mein (naya migration). Branding na ho ya file na mile to purana look, video nahi rukti.
- API: `GET/PUT /channels/{{id}}/branding`. Dashboard ke Channels page par Branding form. Auto production mein bhi branding lagti hai.
- Intro/outro lagne par asli video `video_core.mp4` mein rehti hai, aur quality check usi par hota hai.
- Files `assets/branding/` mein rakhein. Command: `python -m scripts.set_branding <channel id> --highlight "#00FF00" --logo logo.png` (`--show`, `--clear`).
- Live tests: `scripts/try_branding.py`. Total {count} tests.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
t = t.replace("Step 16 par 367 tests", f"Step 17 par {count} tests")
s, e = t.find("**Agla step (Step 17)"), t.find("**Uske baad ke kaam:**")
if s != -1 and e != -1:
    t = t[:s] + ("**Agla step (Step 18): Behtar trend research**: YouTube/Google Trends ke asli data se topics.\n\n") + t[e:]
r.write_text(t, encoding="utf-8")
print("[OK] README mein Step 17 darj")
