import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent

def edit(path, pairs):
    p = root / path
    t = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if t.count(old) != 1:
            print(f"[FAIL] {path}: pattern ek dafa nahi mila: {old[:50]!r}. Kuch nahi badla.")
            raise SystemExit(1)
        t = t.replace(old, new)
    return p, t

# 1) fact_check.py
fp, ft = edit("app/services/fact_check.py", [
    ("    def summary(self) -> str:",
     "    @property\n    def unresolved_wrong(self) -> list[ClaimCheck]:\n"
     "        return [c for c in self.wrong if c.scene_number not in self.fixed_scenes]\n\n"
     "    def summary(self) -> str:"),
])
ft += '''

class FactCheckDraft(BaseModel):
    claims: list[ClaimCheck] = Field(default_factory=list)


FACT_SYSTEM = "You are a careful, conservative fact-checker. Never guess; mark wrong only when confident."


def run_fact_check(board, gemini, auto_fix: bool = True):
    """Pipeline ke liye: Gemini client se check_board chalata hai. (board, report) lautata hai."""
    def ask(prompt):
        return gemini.generate_json(prompt, FactCheckDraft, system=FACT_SYSTEM, temperature=0.2).model_dump()
    return check_board(board, ask, auto_fix=auto_fix)
'''

# 2) pipeline.py
pp, pt = edit("app/pipeline.py", [
    ("from app.services.video_editor import render_video\n",
     "from app.services.video_editor import render_video\n"
     "from app.services.fact_check import FactCheckReport, run_fact_check\n"),
    ("    quality: QualityReport\n\n\ndef slugify",
     "    quality: QualityReport\n    fact_check: FactCheckReport | None = None\n\n\ndef slugify"),
    ("    check_fn=check_video,\n) -> PipelineResult:",
     "    check_fn=check_video,\n    fact_fn=run_fact_check,\n) -> PipelineResult:"),
    ('    _save(run_dir / "storyboard.json", board)\n',
     '    _save(run_dir / "storyboard.json", board)\n\n'
     '    progress("    Fact-check...")\n'
     '    board, fact_report = fact_fn(board, gemini)\n'
     '    _save(run_dir / "fact_check.json", fact_report)\n'
     '    progress("    " + fact_report.summary())\n'
     '    if fact_report.fixed_scenes:\n'
     '        _save(run_dir / "storyboard.json", board)\n'),
    ('status="ready" if report.passed else "needs_review"',
     'status="ready" if report.passed and not fact_report.unresolved_wrong else "needs_review"'),
    ("        quality=report,\n    )",
     "        quality=report,\n        fact_check=fact_report,\n    )"),
])

(root / "output").mkdir(exist_ok=True)
shutil.copy(fp, root / "output" / "fact_check.bak")
shutil.copy(pp, root / "output" / "pipeline.bak")
fp.write_text(ft, encoding="utf-8")
pp.write_text(pt, encoding="utf-8")
print("[OK] fact_check.py aur pipeline.py patch ho gayi")
