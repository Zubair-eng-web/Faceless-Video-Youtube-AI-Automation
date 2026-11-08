import re
from pathlib import Path

r = Path(__file__).resolve().parent.parent / "README.md"
t = r.read_text(encoding="utf-8")
t, n = re.subn(r"Halat: Step \d+ tak mukammal", "Halat: Step 20 tak mukammal", t)
r.write_text(t, encoding="utf-8")
print("[OK] README ki halat Step 20 kar di" if n else "Halat wali line nahi mili, kuch nahi badla")
