"""Long script ki jaanch: lambai, pacing, chapters ka tawazun, hook, dohrayi hui narration/queries.

Sirf report deta hai, kuch badalta nahi. error = script aage nahi barhni chahiye, warning = dekh lein.
"""
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.long_script import LongConfig, LongScript, word_count


class Issue(BaseModel):
    level: str  # "error" ya "warning"
    message: str


class ValidationReport(BaseModel):
    issues: list[Issue] = Field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def validate_script(script: LongScript, cfg: LongConfig | None = None) -> ValidationReport:
    cfg = cfg or LongConfig.from_env()
    issues: list[Issue] = []

    def add(level, msg):
        issues.append(Issue(level=level, message=msg))

    board = script.storyboard
    scenes = board.scenes
    if not scenes:
        add("error", "Script mein koi scene nahi")
        return ValidationReport(issues=issues)

    words = sum(word_count(s.narration) for s in scenes)
    target = script.minutes * cfg.words_per_minute
    ratio = words / target if target else 0
    if ratio < 0.6 or ratio > 1.5:
        add("error", f"Script ki lambai theek nahi: {words} words (target ~{int(target)})")
    elif ratio < 0.8 or ratio > 1.2:
        add("warning", f"Script target se hat kar hai: {words} words (target ~{int(target)})")
    if script.minutes >= 10 and not 1500 <= words <= 3000:
        add("warning", f"10-20 minute ki video ke liye 1500-3000 words chahiye, abhi {words}")
    if script.minutes >= 10 and not 80 <= len(scenes) <= 150:
        add("warning", f"Scenes 80-150 hone chahiye, abhi {len(scenes)}")

    durations = [s.duration for s in scenes]
    avg = sum(durations) / len(durations)
    if not 4 <= avg <= 12:
        add("warning", f"Scene ka average waqt {avg:.1f}s hai (4-12s behtar hai)")
    long_scenes = sum(1 for d in durations if d > 15)
    if long_scenes:
        add("warning", f"{long_scenes} scenes 15 second se lambe hain")

    if script.chapters:
        mean = sum(c.words for c in script.chapters) / len(script.chapters)
        for i, c in enumerate(script.chapters, 1):
            if mean and (c.words < 0.4 * mean or c.words > 2 * mean):
                add("warning", f"Chapter {i} ({c.title}) ka size beqaida hai: {c.words} words (average {int(mean)})")
        if script.chapters[-1].words < 40:
            add("warning", "Aakhri chapter (conclusion) bohat chhota hai")

    hook = (board.hook or "").strip()
    if not hook:
        add("error", "Hook khali hai")
    else:
        if word_count(hook) > 60:
            add("warning", "Hook bohat lamba hai (60 words se zyada)")
        hook_words = {w.strip(".,!?;:\"'").lower() for w in hook.split() if len(w) > 3}
        opening = {w.strip(".,!?;:\"'").lower() for s in scenes[:3] for w in s.narration.split()}
        if hook_words and len(hook_words & opening) / len(hook_words) < 0.3:
            add("warning", "Hook script ke shuru mein nazar nahi aata")

    seen, dups = set(), 0
    for s in scenes:
        key = _norm(s.narration)
        if key in seen:
            dups += 1
        seen.add(key)
    if dups:
        add("warning", f"{dups} scenes ki narration dohra rahi hai")

    queries = [_norm(s.search_query) for s in scenes]
    if len(set(queries)) / len(queries) < 0.7:
        add("warning", f"Search queries dohra rahi hain ({len(set(queries))}/{len(queries)} alag); clips repeat honge")

    return ValidationReport(issues=issues)


def save_validation(report: ValidationReport, run_dir) -> None:
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    (Path(run_dir) / "long_validation.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")