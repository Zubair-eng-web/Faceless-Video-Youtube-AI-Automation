"""Long-form visuals ki jaanch aur credits: kaun se scenes ko weak/repeat clip mili, aur footage ka license/credit.

Sirf report deta hai, kuch badalta nahi. Nateeja visual_report.json aur visual_credits.json mein.
"""
from pathlib import Path

from pydantic import BaseModel, Field


class VisualReport(BaseModel):
    scenes: int = 0
    with_clip: int = 0
    unique_clips: int = 0
    missing: list[int] = Field(default_factory=list)       # clip hi nahi mili
    reused: list[int] = Field(default_factory=list)        # clip pehle bhi lag chuki
    back_to_back: list[int] = Field(default_factory=list)  # lagatar do scenes mein wahi clip
    fallback: list[int] = Field(default_factory=list)      # asli query nahi, asaan query se mili
    generic: list[int] = Field(default_factory=list)       # sirf video ke title se mili (kamzor match)
    portrait: list[int] = Field(default_factory=list)      # 9:16 clip (16:9 mein crop hogi)
    too_short: list[int] = Field(default_factory=list)     # clip scene se chhoti
    warnings: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing

    def summary(self) -> str:
        return (f"{self.with_clip}/{self.scenes} scenes ko clip, {self.unique_clips} alag clips, "
                f"{len(self.reused)} repeat, {len(self.fallback)} fallback, {len(self.generic)} generic, "
                f"{len(self.portrait)} portrait, {len(self.too_short)} chhoti")


class CreditEntry(BaseModel):
    clip_id: int
    provider: str = "Pixabay"
    license: str = "Pixabay License"
    author: str = ""
    page_url: str = ""
    scenes: list[int] = Field(default_factory=list)


def _norm(text) -> str:
    return " ".join((text or "").lower().split())


def build_visual_report(board, clips) -> VisualReport:
    by_scene = {c.scene_number: c for c in clips}
    rep = VisualReport(scenes=len(board.scenes))
    seen: set[int] = set()
    prev = None
    title = _norm(board.title)
    for s in board.scenes:
        c = by_scene.get(s.number)
        if c is None:
            rep.missing.append(s.number)
            prev = None
            continue
        rep.with_clip += 1
        if c.clip_id in seen:
            rep.reused.append(s.number)
        if prev == c.clip_id:
            rep.back_to_back.append(s.number)
        seen.add(c.clip_id)
        prev = c.clip_id
        if _norm(c.query) != _norm(s.search_query):
            (rep.generic if _norm(c.query) == title else rep.fallback).append(s.number)
        if c.portrait or c.height > c.width:
            rep.portrait.append(s.number)
        if c.duration < s.duration:
            rep.too_short.append(s.number)
    rep.unique_clips = len(seen)

    n = max(rep.scenes, 1)
    if rep.missing:
        rep.warnings.append(f"{len(rep.missing)} scenes ko clip nahi mili: {rep.missing[:10]}")
    if rep.back_to_back:
        rep.warnings.append(f"Lagatar wahi clip: scenes {rep.back_to_back[:10]}")
    if len(rep.reused) / n > 0.10:
        rep.warnings.append(f"{len(rep.reused)} scenes mein clip repeat hui (10% se zyada)")
    if len(rep.generic) / n > 0.05:
        rep.warnings.append(f"{len(rep.generic)} scenes ko sirf title se clip mili, match kamzor ho sakta hai")
    if len(rep.fallback) / n > 0.30:
        rep.warnings.append(f"{len(rep.fallback)} scenes asaan query se bane (30% se zyada), visuals dekh lein")
    if rep.portrait:
        rep.warnings.append(f"{len(rep.portrait)} portrait clips 16:9 mein crop hongi")
    return rep


def build_credits(clips) -> list[CreditEntry]:
    out: dict[int, CreditEntry] = {}
    for c in clips:
        e = out.get(c.clip_id)
        if e is None:
            e = out[c.clip_id] = CreditEntry(
                clip_id=c.clip_id, provider=getattr(c, "provider", "Pixabay"),
                license=getattr(c, "license", "Pixabay License"), author=getattr(c, "author", ""),
                page_url=c.page_url)
        if c.scene_number not in e.scenes:
            e.scenes.append(c.scene_number)
    return list(out.values())


def credits_text(credits) -> str:
    """YouTube description ke liye ek chhoti credit line."""
    if not credits:
        return ""
    authors = sorted({c.author for c in credits if c.author}, key=str.lower)[:15]
    line = "Stock footage: Pixabay (https://pixabay.com), Pixabay License."
    if authors:
        line += " Video creators: " + ", ".join(authors) + "."
    return line


def save_visuals(run_dir, board, clips):
    """visual_report.json aur visual_credits.json likhta hai. (report, credits) wapas."""
    rep = build_visual_report(board, clips)
    credits = build_credits(clips)
    run = Path(run_dir)
    run.mkdir(parents=True, exist_ok=True)
    (run / "visual_report.json").write_text(rep.model_dump_json(indent=2), encoding="utf-8")
    (run / "visual_credits.json").write_text("[" + ",".join(c.model_dump_json() for c in credits) + "]",
                                             encoding="utf-8")
    return rep, credits