import re
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
files = {}


def edit(rel, pairs):
    t = files.get(rel) or (root / rel).read_text(encoding="utf-8")
    for old, new in pairs:
        n = t.count(old)
        if n != 1:
            print(f"[FAIL] {rel}: pattern {n} dafa mila: {old[:70]!r}. Kuch nahi badla.")
            raise SystemExit(1)
        t = t.replace(old, new)
    files[rel] = t


if "api_key_mod" in (root / "app/api/main.py").read_text(encoding="utf-8"):
    print("Pehle se patch ho chuka hai")
    raise SystemExit(0)

import sys
sys.path.insert(0, str(root))
from app.services.api_key import field_name
if not field_name():
    print("[FAIL] settings mein gemini key ka field nahi mila. Kuch nahi badla.")
    raise SystemExit(1)
print("Settings field:", field_name())

edit("app/api/main.py", [
    ("from app.services.redo import RedoRequest, default_redo, load_storyboard_view\n",
     "from app.services.redo import RedoRequest, default_redo, load_storyboard_view\n"
     "from app.services import api_key as api_key_mod\n"),
    ('    @app.get("/health")\n',
     '    @app.get("/settings/gemini")\n'
     '    def gemini_key_status(force: bool = False):\n'
     '        return api_key_mod.get_status(force=force)\n\n'
     '    @app.post("/settings/gemini")\n'
     '    def gemini_key_set(body: api_key_mod.KeyBody):\n'
     '        try:\n'
     '            return api_key_mod.set_key(body.key)\n'
     '        except ValueError as exc:\n'
     '            raise HTTPException(422, str(exc)) from exc\n\n'
     '    @app.get("/health")\n'),
])

HEALTH = '    def health(self) -> dict:\n        return self._request("GET", "/health").json()\n'
edit("dashboard/api_client.py", [(HEALTH, HEALTH +
     '\n    def gemini_status(self, force: bool = False) -> dict:\n'
     '        params = {"force": "true"} if force else None\n'
     '        return self._request("GET", "/settings/gemini", params=params).json()\n\n'
     '    def set_gemini_key(self, key: str) -> dict:\n'
     '        return self._request("POST", "/settings/gemini", json={"key": key}).json()\n')])

edit("dashboard/theme.py", [
    ("    if show_header:\n        st.markdown(header_html(), unsafe_allow_html=True)\n",
     "    if show_header:\n        st.markdown(header_html(), unsafe_allow_html=True)\n"
     "    if not os.environ.get(\"PYTEST_CURRENT_TEST\"):\n"
     "        try:\n"
     "            from dashboard.key_panel import show_key_panel\n"
     "            show_key_panel()\n"
     "        except Exception:  # noqa: BLE001 - panel na chale to bhi dashboard chale\n"
     "            pass\n"),
    ("from datetime import datetime\n", "import os\nfrom datetime import datetime\n"),
])

bak = root / "output" / "step22_key_bak"
bak.mkdir(parents=True, exist_ok=True)
for rel in files:
    shutil.copy(root / rel, bak / rel.replace("/", "__"))
for rel, text in files.items():
    (root / rel).write_text(text, encoding="utf-8")

r = root / "README.md"
t = r.read_text(encoding="utf-8")
if "### Step 22" not in t:
    entry = """### Step 22: Gemini API key manager
- `api_key.py`: key ki live jaanch (ek chhoti call, 10 minute cache), nayi key pehle test hoti hai (galat ho to save nahi hoti), phir `.env` mein `GEMINI_API_KEY` update aur usi waqt apply (restart nahi). Free quota khatam hone par alag "limited" halat (key expire nahi samjhi jati).
- API: `GET /settings/gemini` (`?force=true`), `POST /settings/gemini`. Key kabhi poori wapas nahi di jati.
- Dashboard: key expire ya missing ho to upar laal banner aur khali box; sidebar mein "Gemini API key" ka box hamesha.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
    t = re.sub(r"Halat: Step \d+ tak mukammal", "Halat: Step 22 tak mukammal", t)
    r.write_text(t, encoding="utf-8")
print("[OK] 3 files patch ho gayin. Backups: output/step22_key_bak")
