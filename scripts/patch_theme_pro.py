import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
cfg = root / ".streamlit" / "config.toml"
c = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
new = ('[theme]\nbase = "dark"\nprimaryColor = "#6366f1"\nbackgroundColor = "#0b1220"\n'
       'secondaryBackgroundColor = "#111a2e"\ntextColor = "#e6ebf5"\n')
if "[theme]" in c:
    c = re.sub(r"\[theme\].*?(?=\n\[|\Z)", new.rstrip("\n"), c, flags=re.S)
else:
    c = c.rstrip("\n") + "\n\n" + new
cfg.parent.mkdir(exist_ok=True)
cfg.write_text(c.rstrip("\n") + "\n", encoding="utf-8")

r = root / "README.md"
t = r.read_text(encoding="utf-8")
t = re.sub(r"### Step 21: .*?\n", "### Step 21: Professional dashboard UI\n", t, count=1)
t = re.sub(r"- `dashboard/theme\.py`:[^\n]*\n",
           "- `dashboard/theme.py`: professional dark theme (slate background, indigo accent, Inter font), card-style boxes, metric cards, "
           "styled buttons/inputs, brand block aur pill-style menu wala sidebar (hamesha khula), top header bar. `main()` se `inject_theme()` chalta hai; "
           "fail ho to purana look. Rang `theme.py` ke `:root` variables (`--accent`) aur `.streamlit/config.toml` mein badalte hain. Fonts Google Fonts se aate hain.\n",
           t, count=1)
r.write_text(t, encoding="utf-8")
print("[OK] config.toml aur README update ho gaye")
