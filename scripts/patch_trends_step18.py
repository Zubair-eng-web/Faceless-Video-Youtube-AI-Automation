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


if "trends" in (root / "app/agents/research_agent.py").read_text(encoding="utf-8"):
    print("Pehle se patch ho chuka hai")
    raise SystemExit(0)

edit("app/agents/research_agent.py", [
    ('def suggest_topics(niche: str, client, count: int = 5, language: str = "English") -> list[TopicIdea]:',
     'def suggest_topics(niche: str, client, count: int = 5, language: str = "English",\n'
     '                   trends: list[str] | None = None) -> list[TopicIdea]:'),
    ("    result = client.generate_json(prompt, TopicList, system=SYSTEM_PROMPT)",
     "    if trends:\n"
     "        prompt += (\n"
     '            "\\n\\nCurrently popular videos on YouTube (real data, use only as inspiration for what audiences "\n'
     '            "are watching now; ignore anything unrelated to the niche; do not copy titles and do not "\n'
     '            "claim any numbers about them):\\n" + "\\n".join(f"- {t}" for t in trends[:15])\n'
     "        )\n"
     "    result = client.generate_json(prompt, TopicList, system=SYSTEM_PROMPT)"),
])

edit("app/api/runner.py", [
    ("from app.agents.research_agent import suggest_topics\n",
     "from app.agents.research_agent import suggest_topics\nfrom app.services.trends import trend_titles\n"),
    ("topic = pick_topic(suggest_topics(niche, gemini, count=5, language=language), used_topics)",
     "trends = trend_titles(niche, language)\n"
     '        print(f"Trends: {len(trends)} popular titles mile" if trends else "Trends: nahi mile (normal research)", flush=True)\n'
     "        topic = pick_topic(\n"
     "            suggest_topics(niche, gemini, count=5, language=language, **({\"trends\": trends} if trends else {})),\n"
     "            used_topics)"),
])

bak = root / "output" / "step18_bak"
bak.mkdir(parents=True, exist_ok=True)
for rel in files:
    shutil.copy(root / rel, bak / rel.replace("/", "__"))
for rel, text in files.items():
    (root / rel).write_text(text, encoding="utf-8")
print("[OK] research_agent.py aur runner.py patch ho gayin. Backups: output/step18_bak")
