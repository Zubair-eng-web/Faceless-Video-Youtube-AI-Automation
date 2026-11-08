"""Long-form research: outline ke har chapter ke liye web-verified facts aur source links.

Ek hi grounded (Google Search) call poore outline ke liye. Nateeja long_research.json mein save hota hai
(resume), aur facts_for(chapter) har chapter ke script prompt mein jate hain.
Web search na chale to Gemini ke knowledge se facts aate hain, aur warning di jati hai.
Setting: LONG_RESEARCH_GROUNDED (default 1).
"""
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.long_script import Outline, _raw

RESEARCH_SYSTEM = (
    "You are a careful research assistant for documentary-style videos. Report only facts that reliable "
    "sources confirm. Never invent statistics, dates, quotes or names. If sources disagree, leave the fact out."
)
SEARCH_NOTE = ("\n\nUse Google Search to find and verify these facts in reliable sources. "
               "Reply with ONLY the JSON object, no other text.")
MAX_FACTS_PER_CHAPTER = 8


class ResearchFactDraft(BaseModel):
    fact: str
    source: str = ""


class ChapterResearchDraft(BaseModel):
    chapter: int
    facts: list[ResearchFactDraft] = Field(default_factory=list)


class ResearchDraft(BaseModel):
    chapters: list[ChapterResearchDraft] = Field(default_factory=list)


class ResearchFact(BaseModel):
    fact: str
    source: str = ""


class ChapterResearch(BaseModel):
    index: int  # 1 se shuru
    facts: list[ResearchFact] = Field(default_factory=list)


class ResearchReport(BaseModel):
    topic: str = ""
    grounded: bool = False
    chapters: list[ChapterResearch] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)  # search se mile asli links
    warnings: list[str] = Field(default_factory=list)

    @property
    def total_facts(self) -> int:
        return sum(len(c.facts) for c in self.chapters)

    def facts_for(self, idx0: int) -> list[str]:
        """Chapter (0 se shuru) ke facts, source ke naam ke saath."""
        for c in self.chapters:
            if c.index == idx0 + 1:
                return [f"{f.fact} (source: {f.source})" if f.source else f.fact for f in c.facts]
        return []

    def summary(self) -> str:
        how = "web search se" if self.grounded else "Gemini ke knowledge se (web search nahi)"
        return f"{self.total_facts} facts {how}, {len(self.sources)} source links"


def _on(name: str, default: bool = True) -> bool:
    raw = _raw(name)
    return default if raw in (None, "") else raw.strip().lower() not in ("0", "false", "no", "off")


def research_prompt(topic: str, outline: Outline) -> str:
    lines = []
    for i, c in enumerate(outline.chapters, 1):
        pts = "; ".join(c.key_points)
        lines.append(f"{i}. {c.title}: {c.summary}" + (f" | points: {pts}" if pts else ""))
    return (
        f"Research this topic for a documentary-style YouTube video: {topic}\n"
        f"Video title: {outline.title}\n\n"
        "For each chapter below, find 3 to 6 important, verifiable facts from reliable sources "
        "(official, academic, major reference or news sites).\n\nChapters:\n" + "\n".join(lines) + "\n\n"
        "Rules:\n"
        "- Only facts that sources confirm. Never invent numbers, dates, quotes or names.\n"
        "- Each fact is one clear sentence in English. Give exact figures only when sources agree.\n"
        "- source: the website or publisher name.\n"
        "- chapter: the chapter number from the list above.\n"
        'Reply as JSON: {"chapters": [{"chapter": 1, "facts": [{"fact": "...", "source": "..."}]}]}'
    )


def make_research_grounded_fn(gemini):
    """(prompt) -> (text, sources). Google Search tool ke saath ek call."""
    from google.genai import types

    def fn(prompt):
        cfg = types.GenerateContentConfig(
            system_instruction=RESEARCH_SYSTEM, temperature=0.2,
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


def _parse(text):
    text = text or ""
    i, j = text.find("{"), text.rfind("}")
    if i == -1 or j <= i:
        return None
    try:
        draft = ResearchDraft.model_validate_json(text[i:j + 1])
    except ValueError:
        return None
    return draft if draft.chapters else None


def research_long(topic, outline: Outline, gemini, language="English", run_dir=None, grounded_fn=None,
                  grounded=None, progress=print) -> ResearchReport:
    """Outline ke har chapter ke facts. Kabhi exception nahi uthata: fail ho to khali report + warning."""
    run = Path(run_dir) if run_dir else None
    path = run / "long_research.json" if run else None
    if path and path.exists():
        try:
            saved = ResearchReport.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            saved = None
        if saved and saved.chapters and saved.topic == topic:
            progress("Research pehle se hui hai, dobara use kar rahe hain")
            return saved

    n = len(outline.chapters)
    use_web = _on("LONG_RESEARCH_GROUNDED") if grounded is None else grounded
    if use_web and grounded_fn is None:
        try:
            grounded_fn = make_research_grounded_fn(gemini)
        except Exception:  # noqa: BLE001
            grounded_fn = None
    warnings: list[str] = []
    prompt = research_prompt(topic, outline)
    draft, sources, used_web = None, [], False

    progress(f"Research ho rahi hai ({n} chapters)...")
    if use_web and grounded_fn is not None:
        try:
            text, srcs = grounded_fn(prompt + SEARCH_NOTE)
            draft = _parse(text)
            if draft is None:
                draft = gemini.generate_json("Convert this research into the required JSON. Keep every fact.\n\n"
                                             + text, ResearchDraft, system=RESEARCH_SYSTEM, temperature=0.2)
            sources, used_web = list(srcs), True
        except Exception as exc:  # noqa: BLE001
            draft, sources, used_web = None, [], False
            warnings.append(f"Web search research fail ({str(exc)[:90]}), Gemini ke knowledge se facts liye")
    elif use_web:
        warnings.append("Web search tool nahi mila, Gemini ke knowledge se facts liye")

    if draft is None:
        try:
            draft = gemini.generate_json(prompt, ResearchDraft, system=RESEARCH_SYSTEM, temperature=0.2)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Research nahi ho saki ({str(exc)[:90]}); script bina research ke banegi")
            return ResearchReport(topic=topic, warnings=warnings)

    by_idx: dict[int, list[ResearchFact]] = {}
    for c in draft.chapters:
        if 1 <= c.chapter <= n:
            seen = {f.fact for f in by_idx.get(c.chapter, [])}
            for f in c.facts:
                text_ = " ".join((f.fact or "").split())
                if text_ and text_ not in seen:
                    seen.add(text_)
                    by_idx.setdefault(c.chapter, []).append(ResearchFact(fact=text_, source=(f.source or "").strip()))
    chapters = [ChapterResearch(index=i, facts=by_idx[i][:MAX_FACTS_PER_CHAPTER]) for i in sorted(by_idx)]
    for i in range(1, n + 1):
        if i not in by_idx:
            warnings.append(f"Chapter {i} ({outline.chapters[i - 1].title}) ke liye koi fact nahi mila")
    if not used_web and not any("Gemini ke knowledge" in w for w in warnings):
        warnings.append("Facts web search ke baghair aaye (sources nahi)")

    report = ResearchReport(topic=topic, grounded=used_web, chapters=chapters,
                            sources=list(dict.fromkeys(sources)), warnings=warnings)
    if path and chapters:
        run.mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report