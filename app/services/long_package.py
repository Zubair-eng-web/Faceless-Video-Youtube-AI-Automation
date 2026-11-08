"""Long-form YouTube packaging: title, description, chapters, credits, 16:9 thumbnail, metadata."""
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from app.agents.seo_agent import DESCRIPTION_MAX, clean_hashtag, clean_tags, trim_title
from app.core.config import settings
from app.services.long_visuals import build_credits, credits_text
from app.services.thumbnail import extract_frame, make_thumbnail

THUMB_SIZE = (1280, 720)
MIN_CHAPTER_SECONDS = 10.0
MAX_HASHTAGS = 5
SYSTEM = ("You are a YouTube SEO specialist for long educational videos. Write honest, curiosity-driven "
          "titles and descriptions. Never promise what the video does not deliver and never add facts "
          "that are not in the narration.")


class LongSEODraft(BaseModel):
    title: str
    description: str
    hashtags: list[str]
    tags: list[str]
    thumbnail_text: str


class LongPackage(BaseModel):
    title: str
    description: str
    hashtags: list[str]
    tags: list[str]
    thumbnail_text: str
    thumbnail_path: str = ""
    chapters: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def chapter_timestamps(chapters, voiceover, total: float, min_gap: float = MIN_CHAPTER_SECONDS):
    """[(seconds, title)] YouTube ke rules ke mutabiq; 3 se kam bane to khali list."""
    starts = {s.number: s.start_offset for s in voiceover.scenes}
    raw, prev_last = [], 0
    for ch in chapters:
        first = prev_last + 1
        prev_last = ch.last_scene
        if first in starts:
            raw.append((starts[first], ch.title.strip()))
    if raw:
        raw[0] = (0.0, raw[0][1])
    kept = []
    for t, title in raw:
        if kept and t - kept[-1][0] < min_gap:
            continue
        if total - t < min_gap:
            continue
        kept.append((t, title))
    return kept if len(kept) >= 3 else []


def normalize_long_hashtags(tags, max_count: int = MAX_HASHTAGS) -> list[str]:
    out, seen = [], set()
    for t in tags:
        c = clean_hashtag(t)
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
        if len(out) >= max_count:
            break
    return out


def build_description(summary: str, chapters, credits: str, hashtags) -> str:
    tail_parts = []
    if chapters:
        tail_parts.append("Chapters:\n" + "\n".join(f"{fmt_ts(t)} {title}" for t, title in chapters))
    if credits:
        tail_parts.append(credits.strip())
    if hashtags:
        tail_parts.append(" ".join(hashtags))
    tail = "\n\n".join(tail_parts)
    room = DESCRIPTION_MAX - len(tail) - 2
    head = summary.strip()[:max(room, 0)].rstrip()
    return (head + "\n\n" + tail).strip()


def generate_long_seo(board, chapter_titles, client) -> LongSEODraft:
    lang = board.language
    prompt = (
        f"Video title idea: {board.title}\nLanguage: {lang}\n"
        f"Chapters: {'; '.join(chapter_titles)}\n"
        f"Narration:\n{board.full_narration[:9000]}\n\n"
        f"Write the publishing details in {lang}:\n"
        "- title: under 70 characters, curiosity-driven but accurate.\n"
        "- description: 2 short paragraphs summarizing what the viewer will learn, then one line asking to "
        "subscribe. No hashtags, no timestamps.\n"
        "- hashtags: 3 to 5 relevant hashtags, written without the # sign.\n"
        "- tags: 10 to 15 search keywords or short phrases.\n"
        f"- thumbnail_text: 2 to 5 high-impact words in {lang}.\n"
        "Do not add facts that are not in the narration.")
    return client.generate_json(prompt, LongSEODraft, system=SYSTEM, temperature=0.6)


def _font():
    p = Path(settings.fonts_dir) / "arialbd.ttf"
    return p if p.is_file() else None


def build_long_package(script, board, clips, voiceover, run_dir, video_path, client=None, force=False,
                       draft_fn=generate_long_seo, frame_fn=extract_frame, thumb_fn=make_thumbnail,
                       progress=print) -> LongPackage:
    run = Path(run_dir)
    warnings = []
    total = max((s.start_offset + s.duration for s in voiceover.scenes), default=0.0)
    chapters = chapter_timestamps(script.chapters, voiceover, total)
    if not chapters:
        warnings.append("Chapter timestamps nahi bane (3 se kam chapters ya 10s se chhote); poori video par chalega")

    cache = run / "long_seo.json"
    draft = None
    if cache.is_file() and not force:
        try:
            draft = LongSEODraft.model_validate_json(cache.read_text(encoding="utf-8"))
            progress("SEO cache se liya (Gemini request nahi lagi)")
        except ValueError:
            draft = None
    if draft is None:
        draft = draft_fn(board, [c.title for c in script.chapters], client)
        cache.write_text(draft.model_dump_json(indent=2), encoding="utf-8")

    title = trim_title(draft.title)
    summary = re.sub(r"[ \t]*#[^\s#\d]\S*", "", draft.description).strip()
    hashtags = normalize_long_hashtags(draft.hashtags)
    credits = credits_text(build_credits(clips))
    description = build_description(summary, chapters, credits, hashtags)
    words = draft.thumbnail_text.split()[:5] or title.split()[:4]
    thumb_text = " ".join(words)

    video = Path(video_path)
    frame = run / "thumb_frame.jpg"
    thumb = run / "thumbnail.jpg"
    frame_fn(video, min(6.0, max(total / 2, 0.5)), frame)
    thumb_fn(frame, thumb_text, thumb, font_path=_font(), size=THUMB_SIZE)

    pkg = LongPackage(
        title=title, description=description, hashtags=hashtags, tags=clean_tags(draft.tags),
        thumbnail_text=thumb_text, thumbnail_path=str(thumb),
        chapters=[{"seconds": round(t, 2), "time": fmt_ts(t), "title": ti} for t, ti in chapters],
        metadata={"category_id": "27", "privacy": settings.default_privacy, "made_for_kids": False,
                  "language": board.language, "format": "long", "width": 1920, "height": 1080},
        warnings=warnings)
    _validate(pkg, thumb)
    (run / "long_package.json").write_text(pkg.model_dump_json(indent=2), encoding="utf-8")
    return pkg


def _validate(pkg: LongPackage, thumb: Path) -> None:
    from PIL import Image
    w = pkg.warnings
    if not pkg.title:
        w.append("Title khali hai")
    if len(pkg.description) > DESCRIPTION_MAX:
        w.append("Description 5000 characters se lambi hai")
    if len(pkg.tags) < 5:
        w.append(f"Sirf {len(pkg.tags)} tags hain")
    if not pkg.hashtags:
        w.append("Hashtags nahi hain")
    if "Stock footage" not in pkg.description:
        w.append("Description mein credits nahi")
    if thumb.is_file():
        if Image.open(thumb).size != THUMB_SIZE:
            w.append(f"Thumbnail size {Image.open(thumb).size} hai, {THUMB_SIZE} chahiye")
        if thumb.stat().st_size > 2_000_000:
            w.append("Thumbnail 2 MB se bara hai")
    else:
        w.append("Thumbnail nahi bani")
