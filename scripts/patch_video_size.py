import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
bak = root / "output" / "step22_bak"
bak.mkdir(parents=True, exist_ok=True)

theme = root / "dashboard" / "theme.py"
t = theme.read_text(encoding="utf-8")
if "max-height: 520px" in t:
    print("CSS pehle se lagi hui hai")
else:
    anchor = "::-webkit-scrollbar { width: 9px; height: 9px; }"
    if t.count(anchor) != 1:
        print("[FAIL] theme.py mein anchor nahi mila. Kuch nahi badla.")
        raise SystemExit(1)
    css = """/* Video player: khari (9:16) video ko munasib size mein rakho */
div[data-testid="stVideo"] { display:flex; justify-content:center; background:#000; border:1px solid var(--border);
  border-radius:12px; padding:0; overflow:hidden; }
div[data-testid="stVideo"] video, .stVideo video { width:auto !important; height:auto !important; max-width:100% !important;
  max-height: 520px !important; margin:0 auto; display:block; object-fit:contain; background:#000; }
"""
    shutil.copy(theme, bak / "theme.py")
    theme.write_text(t.replace(anchor, css + anchor), encoding="utf-8")
    print("[OK] theme.py mein video size CSS lag gayi")

app = root / "dashboard" / "streamlit_app.py"
a = app.read_text(encoding="utf-8")
old = "    left, right = st.columns(2)\n    with left:\n        if status in HAS_FILES:"
if a.count(old) == 1:
    shutil.copy(app, bak / "streamlit_app.py")
    app.write_text(a.replace(old, old.replace("st.columns(2)", "st.columns([1, 1.7], gap=\"large\")")), encoding="utf-8")
    print("[OK] video detail ka layout theek kiya (video chhota, details bara)")
elif "st.columns([1, 1.7]" in a:
    print("Layout pehle se theek hai")
else:
    print("Layout wala pattern nahi mila, sirf CSS lagi (kaafi hai)")
