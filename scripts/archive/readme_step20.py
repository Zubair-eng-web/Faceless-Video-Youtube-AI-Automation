import re
import sys
from pathlib import Path

count = sys.argv[1] if len(sys.argv) > 1 else "?"
r = Path(__file__).resolve().parent.parent / "README.md"
t = r.read_text(encoding="utf-8")
if "### Step 20" not in t:
    entry = f"""### Step 20: Deployment
- `maintenance.py` + `scripts/maintenance.py`: `data/backups/` mein database ki dated copy (aakhri 7), `logs/*.log` 5 MB se bari ho to `.old`, 14 din se purane rejected/failed/orphan run folders ki list. Published, approved, ready, needs_review folders kabhi nahi chhote jate. Delete sirf `--delete-runs` par.
- `scripts/run_service.ps1` (chhupi window, logs `logs/` mein), `stop_service.ps1`, `install_autostart.ps1` (login par start + roz 3 baje maintenance; `-Remove` se hatana).
- Docker (optional, test nahi hua): `Dockerfile`, `docker-compose.yml` (ports sirf localhost par). YouTube token pehle host par `connect_youtube` se banayen.
- Total {count} tests.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
t = re.sub(r"^\| Deployment \|[^\n]*\n", "", t, flags=re.M)
t = t.replace("| Script/clip edit, dobara chalana | Mukammal | 19 |",
              "| Script/clip edit, dobara chalana | Mukammal | 19 |\n| Deployment, backup, logs | Mukammal | 20 |")
s, e = t.find("**Agla step (Step 20)"), t.find("**Uske baad ke kaam:**")
if s != -1 and e != -1:
    t = t[:s] + "**Agla step (Step 21): Security**: API aur dashboard par login (internet par kholne se pehle zaroori).\n\n" + t[e:]
t = re.sub(r"Step 19 par \d+ tests", f"Step 20 par {count} tests", t)
r.write_text(t, encoding="utf-8")
print("[OK] README mein Step 20 darj")
