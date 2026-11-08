import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
bak = root / "output" / "step22_keyfix_bak"
bak.mkdir(parents=True, exist_ok=True)

theme = root / "dashboard" / "theme.py"
t = theme.read_text(encoding="utf-8")
if "/* Sidebar key box fix */" in t:
    print("CSS pehle se lagi hui hai")
else:
    anchor = "::-webkit-scrollbar { width: 9px; height: 9px; }"
    if t.count(anchor) != 1:
        print("[FAIL] theme.py mein anchor nahi mila. Kuch nahi badla.")
        raise SystemExit(1)
    css = """/* Sidebar key box fix */
section[data-testid="stSidebar"], section[data-testid="stSidebar"][aria-expanded="false"] {
  min-width: 300px !important; width: 300px !important; }
section[data-testid="stSidebar"] div[data-baseweb="input"],
section[data-testid="stSidebar"] div[data-baseweb="base-input"] {
  background: #0d1526 !important; border: 1px solid var(--border) !important; border-radius: 9px !important; }
section[data-testid="stSidebar"] input {
  background: transparent !important; color: var(--text) !important; -webkit-text-fill-color: var(--text) !important;
  font-size: .95rem !important; letter-spacing: normal !important; padding: 10px 12px !important; }
section[data-testid="stSidebar"] input::placeholder { color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; opacity: 1; }
section[data-testid="stSidebar"] div[data-baseweb="input"] button, section[data-testid="stSidebar"] div[data-baseweb="input"] svg {
  color: var(--muted) !important; fill: var(--muted) !important; background: transparent !important; }
section[data-testid="stSidebar"] div[data-testid="stExpander"] summary p { white-space: normal !important; overflow-wrap: anywhere; }
section[data-testid="stSidebar"] div[data-testid="stForm"] { border: none !important; box-shadow: none !important; padding: 0 !important; background: transparent !important; }
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { overflow-wrap: anywhere; font-size: .82rem; }
section[data-testid="stSidebar"] code { overflow-wrap: anywhere; white-space: normal; font-size: .85rem; padding: 2px 6px; }
"""
    shutil.copy(theme, bak / "theme.py")
    theme.write_text(t.replace(anchor, css + anchor), encoding="utf-8")
    print("[OK] theme.py mein sidebar key box CSS lag gayi")

kp = root / "dashboard" / "key_panel.py"
k = kp.read_text(encoding="utf-8")
old = '        st.caption(f"Halat: {LABELS.get(state, state)}  |  Key: {status.get(\'masked\') or \'-\'}")\n'
new = ('        st.markdown(f"**Halat:** {LABELS.get(state, state)}")\n'
       '        masked = status.get("masked")\n'
       '        st.markdown("**Maujooda key:**")\n'
       '        st.code(masked if masked else "set nahi", language=None)\n')
if k.count(old) == 1:
    shutil.copy(kp, bak / "key_panel.py")
    kp.write_text(k.replace(old, new), encoding="utf-8")
    print("[OK] key_panel.py ka halat/key layout theek kiya")
elif "Maujooda key" in k:
    print("key_panel pehle se theek hai")
else:
    print("key_panel ka pattern nahi mila, sirf CSS lagi")
