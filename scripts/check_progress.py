import re, subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent

def has(p):
    return (root / p).exists()

def mark(ok):
    return "[OK]" if ok else "[--]"

def read(p):
    f = root / p
    return f.read_text(encoding="utf-8", errors="ignore") if f.exists() else ""

print("== Option A: Multilingual captions ==")
for f in ["app/services/fonts.py", "assets/fonts/NotoNaskhArabic-Bold.ttf",
          "assets/fonts/NotoSansDevanagari-Bold.ttf", "tests/test_fonts.py",
          "tests/test_captions_multilingual.py", "tests/test_multilingual_script.py",
          "tests/test_multilingual_seo.py", "scripts/try_multilingual.py"]:
    print(mark(has(f)), f)

print("\n== Option B: Background music ==")
bg = read("app/services/background.py")
ve = read("app/services/video_editor.py")
print(mark(has("app/services/background.py")), "background.py")
print(mark("music" in bg.lower()), "background.py mein 'music' ka zikr")
print(mark(any(k in ve.lower() for k in ["duck", "sidechain", "volume"])), "video_editor.py mein music volume/ducking")
print(mark("sfx" in ve.lower() or "sound effect" in ve.lower()), "transition sound effects")
music = [p.name for p in (root / "assets/music").glob("*") if p.suffix.lower() in (".mp3", ".wav")] if has("assets/music") else []
print(mark(bool(music)), f"assets/music mein tracks: {len(music)}")

print("\n== Option C: Variations ==")
for f in ["app/services/variations.py", "app/api/variation_routes.py",
          "tests/test_variations.py", "tests/test_dashboard_variations.py"]:
    print(mark(has(f)), f)
print(mark("variation" in read("app/api/main.py").lower()), "api/main.py mein variation routes juray hain")

print("\n== README ==")
rd = read("README.md")
print(mark("### Step 14" in rd), "Steps log mein Step 14 entry")
print(mark("STEPS-LOG-END" in rd), "STEPS-LOG-END marker")
heads = re.findall(r"^## (\d+)\.", rd, re.M)
print("Maujood sections:", ", ".join(heads))
missing = [str(i) for i in range(1, 18) if str(i) not in heads]
print("Missing sections:", ", ".join(missing) if missing else "koi nahi")

print("\n== Tests ==")
r = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"], cwd=root,
                   capture_output=True, text=True)
tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
print("\n".join(tail))
