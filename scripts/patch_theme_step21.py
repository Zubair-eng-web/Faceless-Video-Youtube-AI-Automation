import re
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
app = root / "dashboard" / "streamlit_app.py"
t = app.read_text(encoding="utf-8")

if "dashboard.theme" in t:
    print("Pehle se patch ho chuka hai")
    raise SystemExit(0)

m = re.search(r"^def main\(\) -> None:\n", t, re.M)
if not m:
    print("[FAIL] 'def main() -> None:' nahi mila. Kuch nahi badla.")
    raise SystemExit(1)

CALL = ("try:\n    from dashboard.theme import inject_theme\n    inject_theme()\n"
        "except Exception:  # theme na chale to bhi dashboard chale\n    pass\n")


def indented(block, ind):
    return "".join(ind + line + "\n" for line in block.splitlines())


body_start = m.end()
tail = t[body_start:]
sp = tail.find("st.set_page_config(")
if sp != -1:  # set_page_config main ke andar hai: theme uske baad
    i, depth = sp + len("st.set_page_config("), 1
    while i < len(tail) and depth:
        depth += {"(": 1, ")": -1}.get(tail[i], 0)
        i += 1
    eol = tail.find("\n", i) + 1
    line_start = tail.rfind("\n", 0, sp) + 1
    ind = tail[line_start:sp]
    insert_at = body_start + eol
else:
    ind = "    "
    insert_at = body_start

t = t[:insert_at] + indented(CALL, ind) + t[insert_at:]

(root / "output").mkdir(exist_ok=True)
bak = root / "output" / "step21_bak"
bak.mkdir(exist_ok=True)
shutil.copy(app, bak / "streamlit_app.py")
app.write_text(t, encoding="utf-8")

cfg = root / ".streamlit" / "config.toml"
cfg.parent.mkdir(exist_ok=True)
c = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
if cfg.exists():
    shutil.copy(cfg, bak / "config.toml")
if "[theme]" not in c:
    c = c.rstrip("\n") + ('\n\n[theme]\nbase = "dark"\nprimaryColor = "#00e5ff"\nbackgroundColor = "#050b14"\n'
                          'secondaryBackgroundColor = "#08182c"\ntextColor = "#d6f6ff"\n').lstrip("\n")
    cfg.write_text(c, encoding="utf-8")
    print("config.toml mein theme jora")
else:
    print("config.toml mein [theme] pehle se hai, chhoda")

r = root / "README.md"
rt = r.read_text(encoding="utf-8")
if "### Step 21" not in rt:
    entry = """### Step 21: Jarvis UI
- `dashboard/theme.py`: dark neon-cyan HUD theme (grid background, glowing panels aur buttons, Orbitron/Rajdhani fonts) aur "J.A.R.V.I.S." header. `streamlit_app.py` ke `main()` se `inject_theme()` chalta hai; fail ho to purana look. Rang badalne ke liye `theme.py` ke `:root` variables (`--c`, `--c2`) aur `.streamlit/config.toml` dekhein. Fonts Google Fonts se aate hain (internet chahiye, warna system fonts).

"""
    rt = rt.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
    rt = re.sub(r"Halat: Step \d+ tak mukammal", "Halat: Step 21 tak mukammal", rt)
    r.write_text(rt, encoding="utf-8")
print("[OK] dashboard patch ho gaya. Backups: output/step21_bak")
