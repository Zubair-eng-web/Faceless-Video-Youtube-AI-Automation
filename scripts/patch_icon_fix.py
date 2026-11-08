import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
theme = root / "dashboard" / "theme.py"
t = theme.read_text(encoding="utf-8")

if "/* Icon font fix */" in t:
    print("Pehle se patch ho chuka hai")
    raise SystemExit(0)

old = ".stApp select, .stApp span {"
anchor = "::-webkit-scrollbar { width: 9px; height: 9px; }"
if t.count(old) != 1 or t.count(anchor) != 1:
    print("[FAIL] theme.py ke patterns nahi mile. Kuch nahi badla.")
    raise SystemExit(1)

css = """/* Icon font fix */
span[data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded,
span[class*="material-symbols"], span[class*="MaterialIcon"] {
  font-family: 'Material Symbols Rounded', 'Material Icons' !important; font-weight: normal !important;
  font-style: normal !important; letter-spacing: normal !important; text-transform: none !important;
  -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga'; white-space: nowrap; }
div[data-testid="stExpander"] summary { display:flex; align-items:center; gap:8px; }
div[data-testid="stExpander"] summary p { margin:0; }
"""
bak = root / "output" / "step22_icon_bak"
bak.mkdir(parents=True, exist_ok=True)
shutil.copy(theme, bak / "theme.py")
t = t.replace(old, ".stApp select {").replace(anchor, css + anchor)
theme.write_text(t, encoding="utf-8")
print("[OK] icon font fix lag gaya")
