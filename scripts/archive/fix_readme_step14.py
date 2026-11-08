import re, shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
p = root / "README.md"
t = p.read_text(encoding="utf-8")
shutil.copy(p, root / "README.bak2.md")

mid = """## 2. Flow

```text
Topic / Niche
   -> Research + Script + Scenes (Gemini)
   -> Voiceover + word timestamps (Edge TTS)
   -> Stock clips (Pixabay)
   -> Video edit + animated captions (FFmpeg)
   -> SEO + Thumbnail + Quality check
   -> Dashboard mein Review (Approve / Reject)
   -> YouTube upload (abhi / schedule / auto)
   -> Analytics + AI recommendations
```

## 3. Features ki halat

| Feature | Halat | Step |
|---|---|---|
| Script, voiceover, clips, editing, captions | Mukammal | 3 se 6 |
| SEO, thumbnail, quality checker | Mukammal | 7 |
| Ek command se pipeline, database, API, dashboard | Mukammal | 8 se 10 |
| YouTube upload, schedule, auto publish | Mukammal | 11, 12 |
| Auto production aur analytics | Mukammal | 13 |
| Multilingual captions (Hindi, Urdu, Arabic) | Mukammal | 14 |
| Multiple variations | Mukammal | 14 |
| Background music, ducking, sound effects | Baqi | 15 |
| Fact-check, trend research, branding | Baqi | Roadmap |
| Dusre platforms, YouTube audit | Baqi | Roadmap |

## 4. Tech stack

Python, FastAPI, Streamlit, SQLite, FFmpeg, Pillow, Gemini API, Edge TTS, Pixabay API, YouTube Data API v3.

## 5. Zarooriyat

- Windows, Python 3.10 ya naya
- FFmpeg aur ffprobe (PATH mein)
- Gemini aur Pixabay ki free API keys
- YouTube upload ke liye Google Cloud project (section 10)

## 6. Setup

1. Virtual environment banayen aur active karein: `python -m venv .venv` phir `.\\.venv\\Scripts\\Activate.ps1`
2. Libraries lagayen: `pip install -r requirements.txt`
3. `.env.example` ko copy kar ke `.env` banayen aur keys bharein.
   Gemini key: https://aistudio.google.com/apikey , Pixabay key: https://pixabay.com/api/docs/
4. Check: `python check_env.py` (aakhir mein "Sab theek hai" aana chahiye).
"""

m = re.search(r"## 2\. Flow.*?4\. Check: `python check_env.py`[^\n]*\n", t, re.S)
if m:
    t = t[:m.start()] + mid + t[m.end():]
    print("Sections 2-6: theek kar diye")
else:
    print("Sections 2-6 ka pattern nahi mila, chhor diya")

if "### Step 14" not in t:
    entry = """### Step 14: Multilingual captions aur multiple variations
- Option A: `fonts.py`, Noto Naskh Arabic aur Noto Sans Devanagari fonts, Hindi/Urdu/Arabic captions ki shaping. Tests: `test_fonts`, `test_captions_multilingual`, `test_multilingual_script`, `test_multilingual_seo`. Live test: `scripts/try_multilingual.py`.
- Option C: `variations.py`, `variation_routes.py` (API mein juray hue), dashboard mein variations. Tests: `test_variations`, `test_dashboard_variations`.
- Total 336 tests.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
    print("Step 14 entry jor di")

road = """**Agla step (Step 15): Background music (Option B)**: mood ke hisab se track chunna, voiceover ke waqt music halki (ducking), transitions par sound effects. Pehle `assets/music` mein kuch royalty-free tracks rakhein.

"""
t, n = re.subn(r"\*\*Step 14 ke liye tin options.*?(?=\*\*Uske baad ke kaam:\*\*)", road, t, flags=re.S)
print("Roadmap:", "update" if n else "pattern nahi mila")

t = re.sub(r"- Hindi, Urdu aur Arabic ke captions ka font abhi nahi lagaya[^\n]*\n",
           "- Hindi, Urdu, Arabic captions ke fonts lag chuke hain (Step 14). Har nayi language ki video khud dekh kar shaping aur right-to-left check karein.\n", t)
t = t.replace("Step 13 par 285 tests", "Step 14 par 336 tests")

p.write_text(t, encoding="utf-8")
