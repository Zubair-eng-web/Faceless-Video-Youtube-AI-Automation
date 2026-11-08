"""Fact-check: script ke dawon ki dobara jaanch (Gemini ka doosra pass).

ask_fn(prompt) -> dict dena chahiye (Gemini ka JSON jawab). Fail hone par video nahi rukti,
sirf report mein error likha jata hai.
"""
from typing import Literal

from pydantic import BaseModel, Field


class ClaimCheck(BaseModel):
    scene_number: int
    claim: str
    verdict: Literal["ok", "doubtful", "wrong"]
    reason: str = ""
    fixed_narration: str | None = None


class FactCheckReport(BaseModel):
    checked: bool = True
    error: str | None = None
    claims: list[ClaimCheck] = Field(default_factory=list)
    fixed_scenes: list[int] = Field(default_factory=list)

    @property
    def wrong(self) -> list[ClaimCheck]:
        return [c for c in self.claims if c.verdict == "wrong"]

    @property
    def doubtful(self) -> list[ClaimCheck]:
        return [c for c in self.claims if c.verdict == "doubtful"]

    @property
    def unresolved_wrong(self) -> list[ClaimCheck]:
        return [c for c in self.wrong if c.scene_number not in self.fixed_scenes]

    def summary(self) -> str:
        if not self.checked:
            return f"Fact-check nahi hua: {self.error}"
        return (f"{len(self.claims)} daway, {len(self.wrong)} ghalat, "
                f"{len(self.doubtful)} shak wale, {len(self.fixed_scenes)} scene theek kiye")


def build_prompt(board) -> str:
    scenes = "\n".join(f"Scene {s.number}: {s.narration}" for s in board.scenes)
    return (
        f"You are a strict fact-checker for a short video script in {board.language}.\n"
        f"Title: {board.title}\n{scenes}\n\n"
        "List every checkable factual claim (numbers, dates, names, scientific facts). "
        "Return JSON: {\"claims\": [{\"scene_number\": int, \"claim\": str, "
        "\"verdict\": \"ok\"|\"doubtful\"|\"wrong\", \"reason\": str, \"fixed_narration\": str|null}]}.\n"
        "Rules: mark \"wrong\" only if you are confident. For \"wrong\", fixed_narration must be the "
        f"whole corrected narration of that scene in {board.language}, with similar length. "
        "For \"ok\" and \"doubtful\", fixed_narration must be null. Do not invent claims."
    )


def _length_ok(old: str, new: str) -> bool:
    a, b = len(old.split()), len(new.split())
    return a > 0 and 0.6 * a <= b <= 1.4 * a


def check_board(board, ask_fn, auto_fix: bool = True):
    """(board, report) lautata hai. Board sirf tab badalta hai jab auto_fix ho aur dawa ghalat ho."""
    try:
        data = ask_fn(build_prompt(board))
        raw = data.get("claims", []) if isinstance(data, dict) else []
    except Exception as e:  # noqa: BLE001 - fact-check se video nahi rukni chahiye
        return board, FactCheckReport(checked=False, error=str(e))

    valid = {s.number for s in board.scenes}
    claims: list[ClaimCheck] = []
    for item in raw:
        try:
            c = ClaimCheck.model_validate(item)
        except Exception:  # noqa: BLE001
            continue
        if c.scene_number in valid:
            claims.append(c)

    report = FactCheckReport(claims=claims)
    if not auto_fix:
        return board, report

    fixes: dict[int, str] = {}
    for c in report.wrong:
        fixed = (c.fixed_narration or "").strip()
        scene = next(s for s in board.scenes if s.number == c.scene_number)
        if fixed and c.scene_number not in fixes and _length_ok(scene.narration, fixed):
            fixes[c.scene_number] = fixed
    if fixes:
        scenes = [s.model_copy(update={"narration": fixes[s.number]}) if s.number in fixes else s
                  for s in board.scenes]
        board = board.model_copy(update={"scenes": scenes})
        report.fixed_scenes = sorted(fixes)
    return board, report


class FactCheckDraft(BaseModel):
    claims: list[ClaimCheck] = Field(default_factory=list)


FACT_SYSTEM = "You are a careful, conservative fact-checker. Never guess; mark wrong only when confident."


def run_fact_check(board, gemini, auto_fix: bool = True):
    """Pipeline ke liye: Gemini client se check_board chalata hai. (board, report) lautata hai."""
    def ask(prompt):
        return gemini.generate_json(prompt, FactCheckDraft, system=FACT_SYSTEM, temperature=0.2).model_dump()
    return check_board(board, ask, auto_fix=auto_fix)
