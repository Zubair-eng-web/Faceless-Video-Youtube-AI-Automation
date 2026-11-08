"""Long-form fact-check: har chapter ko alag, Google Search grounding ke saath (na chale to Gemini ke knowledge se).

Resume: har chapter ka nateeja long_fact_NN.json mein. Grounding ek dafa fail ho to baqi chapters bina grounding.
Settings: LONG_FACTCHECK_GROUNDED (default 1), LONG_FACTCHECK_AUTOFIX (default 1).
"""
import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.fact_check import (FACT_SYSTEM, ClaimCheck, FactCheckDraft, FactCheckReport,
                                     build_prompt, check_board)
from app.services.long_script import LongScript

SEARCH_NOTE = ("\n\nUse Google Search to verify each claim against reliable sources before judging it. "
               "Reply with ONLY the JSON object, no other text.")


class ChapterFact(BaseModel):
    index: int
    title: str
    grounded: bool = False
    sources: list[str] = Field(default_factory=list)
    claims: list[ClaimCheck] = Field(default_factory=list)
    fixes: dict[int, str] = Field(default_factory=dict)  # scene number -> nayi narration


class LongFactReport(BaseModel):
    chapters: list[ChapterFact] = Field(default_factory=list)
    unchecked: list[str] = Field(default_factory=list)  # jin chapters ki jaanch nahi hui
    warnings: list[str] = Field(default_factory=list)

    @property
    def grounded(self) -> bool:
        return bool(self.chapters) and all(c.grounded for c in self.chapters)

    @property
    def sources(self) -> list[str]:
        seen, out = set(), []
        for c in self.chapters:
            for s in c.sources:
                if s not in seen:
                    seen.add(s)
                    out.append(s)
        return out

    @property
    def fixed_scenes(self) -> list[int]:
        return sorted({n for c in self.chapters for n in c.fixes})

    @property
    def unresolved_wrong(self) -> list[ClaimCheck]:
        fixed = set(self.fixed_scenes)
        return [k for c in self.chapters for k in c.claims if k.verdict == "wrong" and k.scene_number not in fixed]

    @property
    def needs_review(self) -> bool:
        return bool(self.unresolved_wrong or self.unchecked or not self.grounded)

    def to_fact_report(self) -> FactCheckReport:
        """Purane dashboard ke format mein (Step 16)."""
        claims = [k for c in self.chapters for k in c.claims]
        if not self.chapters:
            return FactCheckReport(checked=False, error="Koi chapter jaancha nahi gaya")
        err = f"{len(self.unchecked)} chapter jaanch nahi hue" if self.unchecked else None
        return FactCheckReport(checked=True, error=err, claims=claims, fixed_scenes=self.fixed_scenes)

    def summary(self) -> str:
        claims = [k for c in self.chapters for k in c.claims]
        wrong = sum(1 for k in claims if k.verdict == "wrong")
        doubt = sum(1 for k in claims if k.verdict == "doubtful")
        how = "web search se" if self.grounded else "Gemini ke knowledge se (web search nahi)"
        extra = f", {len(self.unchecked)} chapter jaanch nahi hue" if self.unchecked else ""
        return (f"{len(claims)} daway {how}: {wrong} ghalat, {doubt} shak wale, "
                f"{len(self.fixed_scenes)} scene theek kiye, {len(self.sources)} sources{extra}")


def _env_on(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    return default if raw in (None, "") else raw.strip().lower() not in ("0", "false", "no", "off")


def extract_json(text):
    """Jawab mein se pehla JSON object (code fence ke saath bhi). Na mile to None."""
    text = (text or "").strip()
    i, j = text.find("{"), text.rfind("}")
    if i == -1 or j <= i:
        return None
    try:
        data = json.loads(text[i:j + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("claims"), list) else None


def make_grounded_fn(gemini):
    """(prompt) -> (text, sources). Google Search tool ke saath ek call."""
    from google.genai import types

    def fn(prompt):
        cfg = types.GenerateContentConfig(
            system_instruction=FACT_SYSTEM, temperature=0.2,
            tools=[types.Tool(google_search=types.GoogleSearch())])
        resp = gemini._client.models.generate_content(model=gemini.model, contents=prompt, config=cfg)
        sources = []
        try:
            for cand in resp.candidates or []:
                meta = getattr(cand, "grounding_metadata", None)
                for ch in (getattr(meta, "grounding_chunks", None) or []):
                    web = getattr(ch, "web", None)
                    if web and getattr(web, "uri", None):
                        sources.append(f"{web.title} - {web.uri}" if getattr(web, "title", None) else web.uri)
        except Exception:  # noqa: BLE001 - sources na milen to bhi jawab theek hai
            pass
        return resp.text or "", sources

    return fn


def _plain(gemini, prompt) -> dict:
    return gemini.generate_json(prompt, FactCheckDraft, system=FACT_SYSTEM, temperature=0.2).model_dump()


def fact_check_long(script: LongScript, gemini, run_dir=None, grounded_fn=None, grounded=None,
                    auto_fix=None, progress=print):
    """(naya storyboard, LongFactReport). Run folder ho to fact_check.json aur storyboard.json bhi likhta hai."""
    board = script.storyboard
    auto_fix = _env_on("LONG_FACTCHECK_AUTOFIX") if auto_fix is None else auto_fix
    use_web = _env_on("LONG_FACTCHECK_GROUNDED") if grounded is None else grounded
    if use_web and grounded_fn is None:
        try:
            grounded_fn = make_grounded_fn(gemini)
        except Exception:  # noqa: BLE001
            grounded_fn = None
    state = {"web": use_web and grounded_fn is not None}
    run = Path(run_dir) if run_dir else None
    report = LongFactReport()
    if use_web and grounded_fn is None:
        report.warnings.append("Web search tool nahi mila, Gemini ke knowledge se jaanch hui")

    fixes_all: dict[int, str] = {}
    for idx, info in enumerate(script.chapters, 1):
        path = run / f"long_fact_{idx:02d}.json" if run else None
        saved = None
        if path and path.exists():
            try:
                saved = ChapterFact.model_validate_json(path.read_text(encoding="utf-8"))
            except ValueError:
                saved = None
        if saved:
            progress(f"Fact-check {idx}/{len(script.chapters)} pehle se hua hai")
            report.chapters.append(saved)
            fixes_all.update(saved.fixes)
            continue

        sub = board.model_copy(update={"scenes": [s for s in board.scenes
                                                  if info.first_scene <= s.number <= info.last_scene]})
        sources: list[str] = []
        used_web = {"v": False}

        def ask(prompt):
            if state["web"]:
                try:
                    text, srcs = grounded_fn(prompt + SEARCH_NOTE)
                    data = extract_json(text)
                    if data is None:
                        data = _plain(gemini, "Convert this fact-check into the required JSON. Keep every claim; "
                                              "fixed_narration only for wrong claims.\n\n" + text)
                    sources.extend(srcs)
                    used_web["v"] = True
                    return data
                except Exception as exc:  # noqa: BLE001 - grounding fail: baqi chapters bina web search
                    state["web"] = False
                    report.warnings.append(f"Web search band ho gayi ({str(exc)[:90]}), baqi chapters Gemini ke "
                                           "knowledge se jaanche gaye")
            return _plain(gemini, prompt)

        progress(f"Fact-check {idx}/{len(script.chapters)}: {info.title}...")
        new_sub, rep = check_board(sub, ask, auto_fix=auto_fix)
        if not rep.checked:
            report.unchecked.append(info.title)
            report.warnings.append(f"Chapter {idx} ({info.title}) jaanch nahi hua: {rep.error}")
            continue
        old = {s.number: s.narration for s in sub.scenes}
        fixes = {s.number: s.narration for s in new_sub.scenes if s.narration != old[s.number]}
        fact = ChapterFact(index=idx, title=info.title, grounded=used_web["v"], sources=list(dict.fromkeys(sources)),
                           claims=rep.claims, fixes=fixes)
        report.chapters.append(fact)
        fixes_all.update(fixes)
        if path:
            path.write_text(fact.model_dump_json(indent=2), encoding="utf-8")

    if fixes_all:
        board = board.model_copy(update={"scenes": [s.model_copy(update={"narration": fixes_all[s.number]})
                                                    if s.number in fixes_all else s for s in board.scenes]})
    if run:
        run.mkdir(parents=True, exist_ok=True)
        (run / "fact_check.json").write_text(report.to_fact_report().model_dump_json(indent=2), encoding="utf-8")
        (run / "long_fact_check.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        if fixes_all:
            (run / "storyboard.json").write_text(board.model_dump_json(indent=2), encoding="utf-8")
    return board, report
