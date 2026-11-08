import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent

def edit(path, pairs):
    p = root / path
    t = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if t.count(old) != 1:
            print(f"[FAIL] {path}: pattern {t.count(old)} dafa mila: {old[:50]!r}. Kuch nahi badla.")
            raise SystemExit(1)
        t = t.replace(old, new)
    return p, t

api_p, api_t = edit("app/api/main.py", [
    ('REVIEWABLE = {"ready", "needs_review"}\n',
     'REVIEWABLE = {"ready", "needs_review"}\n\n\n'
     'def load_fact_check(run_dir):\n'
     '    """Run folder se fact_check.json parhna (nahi mili ya kharab ho to None)."""\n'
     '    if not run_dir:\n'
     '        return None\n'
     '    f = Path(run_dir) / "fact_check.json"\n'
     '    try:\n'
     '        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None\n'
     '    except (OSError, ValueError):\n'
     '        return None\n'),
    ('    out["quality"] = json.loads(row["quality_json"]) if row["quality_json"] else None\n',
     '    out["quality"] = json.loads(row["quality_json"]) if row["quality_json"] else None\n'
     '    out["fact_check"] = load_fact_check(row["run_dir"])\n'),
])

dash_p, dash_t = edit("dashboard/streamlit_app.py", [
    ("def video_detail(client: ApiClient, video_id: int) -> None:",
     'def show_fact_check(fc) -> None:\n'
     '    if not fc:\n'
     '        return\n'
     '    if not fc.get("checked", True):\n'
     '        st.caption("Fact-check nahi hua: " + str(fc.get("error")))\n'
     '        return\n'
     '    claims = fc.get("claims", [])\n'
     '    fixed = set(fc.get("fixed_scenes", []))\n'
     '    bad = [c for c in claims if c.get("verdict") != "ok"]\n'
     '    st.write("Fact-check:", f"{len(claims)} daway, {len(bad)} par shak ya ghalti")\n'
     '    for c in bad:\n'
     '        tag = "GHALAT" if c.get("verdict") == "wrong" else "SHAK"\n'
     '        extra = " (khud theek kiya)" if c.get("scene_number") in fixed else ""\n'
     '        st.warning(f"{tag} scene {c.get(\'scene_number\')}{extra}: {c.get(\'claim\')} | {c.get(\'reason\', \'\')}")\n\n\n'
     "def video_detail(client: ApiClient, video_id: int) -> None:"),
    ("            for line in lines:\n                st.caption(line)\n",
     "            for line in lines:\n                st.caption(line)\n"
     '        show_fact_check(video.get("fact_check"))\n'),
])

(root / "output").mkdir(exist_ok=True)
shutil.copy(api_p, root / "output" / "api_main.bak")
shutil.copy(dash_p, root / "output" / "streamlit_app.bak")
api_p.write_text(api_t, encoding="utf-8")
dash_p.write_text(dash_t, encoding="utf-8")

# README Step 16
r = root / "README.md"
t = r.read_text(encoding="utf-8")
if "### Step 16" not in t:
    entry = """### Step 16: Fact-check
- `fact_check.py`: script ke dawon ki Gemini se dobara jaanch (ok / doubtful / wrong). Confident ghalat scene ki narration khud theek hoti hai (lambai 60% se 140% ke andar), shak wale daway kabhi nahi badalte. Gemini fail ho to video nahi rukti.
- Pipeline: script ke baad, voiceover se pehle. `fact_check.json` bani hai aur `result.json` mein bhi. Na theek hone wala ghalat dawa ho to status `needs_review`.
- API `fact_check` field deta hai, dashboard video detail mein ghalat aur shak wale daway scene ke saath dikhte hain.
- Live test: `scripts/try_factcheck.py` (sirf report, auto-fix band). Total 368 tests.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
t = t.replace("| Fact-check | Ban raha hai | 16 |", "| Fact-check | Mukammal | 16 |")
s, e = t.find("**Agla step (Step 16)"), t.find("**Uske baad ke kaam:**")
if s != -1 and e != -1:
    t = t[:s] + ("**Agla step (Step 17): Channel branding**: har channel ke captions ka rang aur font, "
                 "logo watermark, intro/outro.\n\n") + t[e:]
t = t.replace("Step 15 par 355 tests", "Step 16 par 368 tests")
r.write_text(t, encoding="utf-8")
print("[OK] API, dashboard aur README patch ho gaye")
