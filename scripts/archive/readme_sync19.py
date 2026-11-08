"""README ko Step 19 tak sahi karna: header, features, endpoints, pages, roadmap, limits aur folder structure.
Chalane ka tareeqa: python -m scripts.readme_sync19 406
(ye script dobara chalane par kuch nahi bigarti, har cheez pehle check karti hai)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
MARKER = "<!-- STEPS-LOG-END -->"

SKIP_DIRS = {".venv", ".pytest_cache", "__pycache__", ".git", ".mypy_cache", "node_modules"}
DIRS_ONLY = {"output", "assets/cache"}
HIDE_CHILDREN = {"assets/music", "data/tokens"}
SKIP_FILE = re.compile(r"(\.bak\d*\.md$|\.bak\.md$|\.pyc$|\.zip$|\.json\.json$|^README\.step\d+\.bak\.md$)")
SKIP_SCRIPT = re.compile(r"^(patch_.*|fix_.*|readme_step\d+)\.py$")

T_MID, T_END, T_BAR, T_GAP = "\u251c\u2500\u2500 ", "\u2514\u2500\u2500 ", "\u2502   ", "    "


def tree_lines(folder, rel="", prefix=""):
    entries = []
    for p in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
        sub = f"{rel}/{p.name}" if rel else p.name
        if p.is_dir():
            if p.name in SKIP_DIRS:
                continue
            entries.append((0, p, sub))
        else:
            if rel in DIRS_ONLY or SKIP_FILE.search(p.name):
                continue
            if rel == "scripts" and SKIP_SCRIPT.match(p.name):
                continue
            entries.append((1, p, sub))
    entries.sort(key=lambda e: (e[0], e[1].name == "__init__.py", e[1].name.lower()))
    lines = []
    for i, (is_file, p, sub) in enumerate(entries):
        last = i == len(entries) - 1
        lines.append(prefix + (T_END if last else T_MID) + p.name + ("" if is_file else "/"))
        if not is_file and sub not in HIDE_CHILDREN:
            lines += tree_lines(p, sub, prefix + (T_GAP if last else T_BAR))
    return lines


def build_structure():
    body = "\n".join([f"{ROOT.name}/"] + tree_lines(ROOT))
    return (
        "## Folder structure\n\n```text\n" + body + "\n```\n\n"
        "`assets/cache/`, `data/tokens/` aur `output/` ke andar cache, local tokens aur generated test/run files hain. "
        "`scripts/` mein `patch_*.py`, `fix_*.py` aur `readme_step*.py` purani one-time scripts hain (yahan nahi dikhayi gayin). "
        "`.venv/` aur `.pytest_cache/` local environment hain.\n"
    )


STEP19 = """### Step 19: Script/clip edit aur dobara chalana
- `redo.py`: video ko uske run folder se dobara banata hai. Narration badli to voiceover, fact-check (sirf report, text khud nahi badalta) aur SEO dobara; query badli to sirf us scene ki clip. Pehle se bani `voiceover.json`, `clips.json`, `seo.json` dobara use hoti hain, sirf missing hissa banta hai, phir render, thumbnail aur quality check.
- Fail hui video ka run folder ab database mein save hota hai (`pipeline.LAST_RUN_DIR`), is liye wahin se resume ho sakti hai. Purani failed videos ka folder maujood nahi.
- API: `GET /videos/{id}/storyboard`, `POST /videos/{id}/redo` (statuses ready, needs_review, failed se). Dashboard video detail mein "Script/clips edit karein ya dobara banayen" panel.
- Render se pehle purani `video_core.mp4` hat jati hai, taake quality check purani video par na ho.
- Total {count} tests.
"""

STEP20 = ("**Agla step (Step 20):** Dusre platforms ke liye export folder (Reels/TikTok) aur Deployment "
          "(database backup, logs). Tafseel neeche table mein.")


def sub1(text, pattern, repl, flags=0):
    return re.sub(pattern, lambda m: repl, text, count=1, flags=flags)


def sync(text, count):
    text = sub1(text, r"^Halat: Step \d+ tak", "Halat: Step 19 tak", re.M)

    if "### Step 19" not in text:
        if MARKER not in text:
            raise SystemExit("[FAIL] STEPS-LOG-END marker README mein nahi mila")
        text = text.replace(MARKER, STEP19.replace("{count}", count) + "\n" + MARKER, 1)

    if not re.search(r"^\|[^|\n]*\|\s*Mukammal\s*\|\s*19\s*\|", text, re.M):
        text = sub1(text, r"^(\| Trend research \|[^\n]*\n)",
                    "| Trend research | Mukammal | 18 |\n| Script/clip edit, dobara chalana | Mukammal | 19 |\n", re.M)

    if "| `GET /channels/{id}/branding`" not in text:
        text = sub1(text, r"^(\| `PUT /channels/\{id\}/schedule`[^\n]*\n)",
                    "| `PUT /channels/{id}/schedule` | Roz kitni videos, kis waqt, kitni lambi |\n"
                    "| `GET /channels/{id}/branding`, `PUT /channels/{id}/branding` | Channel ki branding (rang, logo, intro/outro) |\n"
                    "| `POST /channels/{id}/variations` | Ek topic ki kai languages mein videos |\n", re.M)
    if "| `GET /videos/{id}/storyboard`" not in text:
        text = sub1(text, r"^(\| `GET /videos`, `GET /videos/\{id\}`[^\n]*\n)",
                    "| `GET /videos`, `GET /videos/{id}` | List (status/channel filter) aur tafseel (SEO, quality, fact-check) |\n"
                    "| `GET /videos/{id}/storyboard`, `POST /videos/{id}/redo` | Script dekhna, scenes edit kar ke ya bina badlav dobara banana/resume |\n", re.M)

    if "**Variations:**" not in text:
        text = sub1(text, r"^- \*\*Channels:\*\*[^\n]*",
                    "- **Channels:** channel banana ya hatana, aur har channel ki Branding (rang, logo, intro/outro).", re.M)
        text = sub1(text, r"^(- \*\*Analytics:\*\*[^\n]*)",
                    "- **Analytics:** views, likes, comments, engagement aur AI recommendations.\n"
                    "- **Variations:** ek topic ki kai languages mein alag alag videos.", re.M)
        text = sub1(text, r"(Jo videos ban rahi hon unka progress har 5 second mein update hota hai\.)",
                    "Script/clips edit karna aur fail hui video dobara chalana. Jo videos ban rahi hon unka progress har 5 second mein update hota hai.")

    text = sub1(text, r"Step \d+ par \d+ tests hone chahiye", f"Step 19 par {count} tests hone chahiye")

    text = re.sub(r"^\| (Fact-check step|Dashboard behtari) \|[^\n]*\n", "", text, flags=re.M)
    text = sub1(text, r"^\*\*Agla step \(Step \d+\)[^\n]*", STEP20, re.M)
    text = re.sub(r"^\*\*Step \d+ ke liye tin options[^\n]*\n", "", text, flags=re.M)

    text = sub1(text, r"^- Topics Gemini ke general knowledge se aate hain[^\n]*",
                "- Topic chunne ke liye YouTube ki trending titles istemal hoti hain (channel connect ho aur quota bacha ho), "
                "warna Gemini ke general knowledge se. Gemini kabhi kabhi ghalat facts likh deta hai, is liye Approve se pehle facts khud dekhein.", re.M)
    if "Step 19 se pehle" not in text:
        text = sub1(text, r"^(- Pixabay ki shart[^\n]*)",
                    "- Step 19 se pehle ki failed videos ka run folder database mein nahi, wo resume nahi ho sakti, nayi video banayen.\n"
                    "- Pixabay ki shart ke mutabiq search results 24 ghante se zyada cache nahi kiye jate.", re.M)

    start = text.find("## Folder structure")
    head = text if start == -1 else text[:start].rstrip("\n") + "\n\n"
    return head + build_structure()


def main():
    count = sys.argv[1] if len(sys.argv) > 1 else "406"
    before = README.read_text(encoding="utf-8-sig")
    after = sync(before, count)
    if after == before:
        print("[OK] README pehle se sahi hai, kuch nahi badla")
        return
    (ROOT / "README.step19.bak.md").write_text(before, encoding="utf-8")
    README.write_text(after, encoding="utf-8")
    print(f"[OK] README Step 19 tak update ho gayi ({count} tests). Purani copy: README.step19.bak.md")


if __name__ == "__main__":
    main()
