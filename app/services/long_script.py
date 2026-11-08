"""Long-form script: outline -> chapter by chapter -> Storyboard (scenes).

Sab settings environment variables se (LONG_*). Run folder ho to outline aur har chapter file mein save hota
hai, aur dobara chalane par bane hue chapters dobara nahi likhe jate (free API calls bachti hain).
"""
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.config import BASE_DIR
from app.core.models import Scene, SceneDraft, Storyboard



class LongScriptError(RuntimeError):
    pass


def _dotenv_value(name):
    """.env file se ek key parhna, os.environ ko chhue baghair."""
    try:
        for line in (BASE_DIR / ".env").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key.strip() == name:
                    return value.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def _raw(name):
    raw = os.getenv(name)
    return raw if raw not in (None, "") else _dotenv_value(name)


def _env(name, default, cast):
    raw = _raw(name)
    if raw in (None, ""):
        return default
    try:
        return cast(raw)
    except ValueError:
        return default

class LongConfig(BaseModel):
    words_per_minute: int = 150
    scene_seconds: float = 7.0
    max_scene_words: int = 32
    min_minutes: float = 3.0
    max_minutes: float = 20.0
    max_scenes: int = 150
    model: str | None = None  # None = GeminiClient ka default model

    @classmethod
    def from_env(cls) -> "LongConfig":
        return cls(
            words_per_minute=_env("LONG_WORDS_PER_MINUTE", 150, int),
            scene_seconds=_env("LONG_SCENE_SECONDS", 7.0, float),
            max_scene_words=_env("LONG_MAX_SCENE_WORDS", 32, int),
            min_minutes=_env("LONG_MIN_MINUTES", 3.0, float),
            max_minutes=_env("LONG_MAX_MINUTES", 20.0, float),
            max_scenes=_env("LONG_MAX_SCENES", 150, int),
            model=_raw("LONG_GEMINI_MODEL") or None,
        )


class SeriesStyle(BaseModel):
    """Series ki yaksan shakhsiyat: har episode isi style mein likha jata hai."""
    name: str = ""
    narrator: str = "calm, clear, curious documentary narrator"
    tone: str = "informative and engaging, never clickbait"
    audience: str = "general curious viewers"
    episode: int | None = None


class ChapterPlan(BaseModel):
    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)


class Outline(BaseModel):
    title: str
    hook: str
    chapters: list[ChapterPlan]


class ChapterDraft(BaseModel):
    scenes: list[SceneDraft]


class ChapterInfo(BaseModel):
    title: str
    first_scene: int
    last_scene: int
    words: int


class LongScript(BaseModel):
    storyboard: Storyboard
    chapters: list[ChapterInfo]
    minutes: float
    words: int
    warnings: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = (
    "You are a senior documentary scriptwriter for long YouTube videos. You write accurate, well-paced, spoken "
    "narration. Use only well-established facts. Never invent statistics, quotes, dates or names. If you are not "
    "sure about a detail, leave it out or speak in general terms. Never mention chapters, scenes or the script itself."
)


def clamp_minutes(minutes: float, cfg: LongConfig) -> float:
    return max(cfg.min_minutes, min(cfg.max_minutes, float(minutes)))


def chapter_count(minutes: float) -> int:
    return max(4, min(10, round(minutes / 2)))


def chapter_targets(total_words: int, n: int) -> list[int]:
    """Pehla aur aakhri chapter thora chhota, baqi barabar."""
    weights = [0.8 if i in (0, n - 1) else 1.0 for i in range(n)]
    s = sum(weights)
    return [max(40, round(total_words * w / s)) for w in weights]


def words_per_scene(cfg: LongConfig) -> float:
    return cfg.scene_seconds * cfg.words_per_minute / 60


def word_count(text: str) -> int:
    return len((text or "").split())


def split_scene(text: str, max_words: int) -> list[str]:
    """Lambi narration ko jumlon par toro (har tukra max_words se chhota, jahan mumkin ho)."""
    text = " ".join((text or "").split())
    if word_count(text) <= max_words:
        return [text] if text else []
    sentences = re.split(r"(?<=[.!?\u0964\u06d4\u061f])\s+", text)
    pieces, cur = [], []
    for s in sentences:
        sw = s.split()
        if cur and len(cur) + len(sw) > max_words:
            pieces.append(" ".join(cur))
            cur = []
        cur += sw
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def _style_block(style: SeriesStyle) -> str:
    lines = [f"Narrator voice: {style.narrator}.", f"Tone: {style.tone}.", f"Audience: {style.audience}."]
    if style.name:
        lines.insert(0, f"This is an episode of the series '{style.name}'"
                        + (f" (episode {style.episode})." if style.episode else "."))
    return "\n".join(lines)


def _facts_block(facts) -> str:
    if not facts:
        return ""
    return ("Verified research facts for this chapter (from reliable web sources). Build the factual statements "
            "on these and do not contradict them:\n" + "\n".join(f"- {f}" for f in facts) + "\n")


def outline_prompt(topic, language, minutes, n_chapters, style, note="") -> str:
    return (
        f"Plan a {minutes:g}-minute educational YouTube video about: {topic}\n"
        f"Language of title, hook and chapters: {language}.\n{_style_block(style)}\n\n"
        f"Create exactly {n_chapters} chapters in a logical story order: an engaging opening chapter, "
        "progressively deeper middle chapters, and a closing chapter that wraps up.\n"
        "- title: a specific, honest video title.\n"
        "- hook: the first 1 to 2 spoken sentences that make people stay.\n"
        "- each chapter: title, a 1 to 2 sentence summary, and 3 to 5 key_points (concrete facts or ideas to cover).\n"
        "Chapters must not overlap: every key point belongs to one chapter only." + note
    )


def chapter_prompt(topic, language, style, outline, idx, target_words, target_scenes, prev_tail, note="", facts=None) -> str:
    ch = outline.chapters[idx]
    n = len(outline.chapters)
    listing = "\n".join(f"{i + 1}. {c.title}: {c.summary}" for i, c in enumerate(outline.chapters))
    points = "\n".join(f"- {p}" for p in ch.key_points) or "- (cover the summary)"
    opening = (f"This is the FIRST chapter. Start with this hook, naturally: {outline.hook}\n" if idx == 0 else "")
    closing = ("This is the LAST chapter. End with a short, satisfying conclusion and a light invitation to "
               "subscribe.\n" if idx == n - 1 else "")
    prev = f"The previous chapter ended with: \"{prev_tail}\"\nContinue smoothly from it.\n" if prev_tail else ""
    return (
        f"Video topic: {topic}\nVideo title: {outline.title}\nNarration language: {language}\n"
        f"{_style_block(style)}\n\nFull outline (for context, do not repeat other chapters):\n{listing}\n\n"
        f"Now write chapter {idx + 1} of {n}: {ch.title}\nSummary: {ch.summary}\nCover these points:\n{points}\n\n"
        f"{opening}{closing}{prev}{_facts_block(facts)}"
        f"Length: about {target_words} spoken words in total, split into about {target_scenes} scenes.\n"
        "For each scene give:\n"
        f"- narration: 1 to 3 natural spoken sentences (about {max(8, round(target_words / max(target_scenes, 1)))} "
        f"words) in {language}. No stage directions, no markdown.\n"
        "- visual_description: what the viewer should see, concrete and filmable.\n"
        "- search_query: 2 to 4 ENGLISH words for a stock footage search (concrete nouns, no abstract words), "
        "different for every scene.\n"
        "Do not repeat facts already used in other chapters." + note
    )


def _ask(client, prompt, schema, temperature):
    try:
        return client.generate_json(prompt, schema, system=SYSTEM_PROMPT, temperature=temperature)
    except Exception as exc:  # noqa: BLE001
        raise LongScriptError(str(exc)) from exc


def _load(path, model):
    if path is None:
        return None
    try:
        return model.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(path, model):
    if path is not None:
        Path(path).write_text(model.model_dump_json(indent=2), encoding="utf-8")


def make_client(cfg: LongConfig | None = None):
    from app.services.gemini_client import make_gemini_client
    cfg = cfg or LongConfig.from_env()
    return make_gemini_client(cfg.model)


def get_outline(topic, client, minutes, language, style, cfg, run_dir, progress, warnings) -> Outline:
    path = Path(run_dir) / "long_outline.json" if run_dir else None
    outline = _load(path, Outline)
    if outline and len(outline.chapters) >= 3:
        progress("Outline pehle se bana hua hai, dobara use kar rahe hain")
        return outline
    want = chapter_count(minutes)
    note = ""
    for attempt in (1, 2):
        progress(f"Outline ban raha hai ({want} chapters)...")
        outline = _ask(client, outline_prompt(topic, language, minutes, want, style, note), Outline, 0.8)
        chapters = [c for c in outline.chapters if c.title.strip()]
        if 3 <= len(chapters) <= 14:
            outline = outline.model_copy(update={"chapters": chapters})
            if len(chapters) != want:
                warnings.append(f"Outline mein {len(chapters)} chapters aaye (maanga {want})")
            _save(path, outline)
            return outline
        note = f"\nIMPORTANT: your last answer had {len(chapters)} chapters; give exactly {want}."
    raise LongScriptError(f"Outline mein chapters ki ginti theek nahi ({len(chapters)})")


def get_chapter(topic, client, language, style, outline, idx, target_words, cfg, run_dir, prev_tail, progress, warnings, facts=None):
    path = Path(run_dir) / f"long_chapter_{idx + 1:02d}.json" if run_dir else None
    draft = _load(path, ChapterDraft)
    title = outline.chapters[idx].title
    if draft and draft.scenes:
        progress(f"Chapter {idx + 1}/{len(outline.chapters)} pehle se bana hua hai")
        return draft
    target_scenes = max(2, round(target_words / words_per_scene(cfg)))
    note = ""
    best = None
    for attempt in (1, 2):
        progress(f"Chapter {idx + 1}/{len(outline.chapters)}: {title}...")
        draft = _ask(client, chapter_prompt(topic, language, style, outline, idx, target_words, target_scenes,
                                            prev_tail, note, facts), ChapterDraft, 0.7)
        scenes = [s for s in draft.scenes if word_count(s.narration) > 0]
        words = sum(word_count(s.narration) for s in scenes)
        if scenes:
            best = ChapterDraft(scenes=scenes)
            if 0.6 * target_words <= words <= 1.5 * target_words:
                _save(path, best)
                return best
        note = (f"\nIMPORTANT: your last answer had {words} words; write about {target_words} words "
                f"(about {target_scenes} scenes).")
    words = sum(word_count(s.narration) for s in best.scenes) if best else 0
    if best is None or not (0.4 * target_words <= words <= 2 * target_words):
        raise LongScriptError(f"Chapter {idx + 1} ({title}) ki lambai theek nahi ({words} words, chahiye {target_words})")
    warnings.append(f"Chapter {idx + 1} ({title}): {words} words (target {target_words})")
    _save(path, best)
    return best


def generate_long_script(topic, client, minutes=10, language="English", style=None, run_dir=None,
                         cfg=None, progress=print, researcher=None) -> LongScript:
    topic = " ".join((topic or "").split())
    if not topic:
        raise ValueError("Topic khali hai")
    cfg = cfg or LongConfig.from_env()
    style = style or SeriesStyle()
    minutes = clamp_minutes(minutes, cfg)
    if run_dir:
        Path(run_dir).mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    outline = get_outline(topic, client, minutes, language, style, cfg, run_dir, progress, warnings)
    research = researcher(outline) if researcher else None
    total_words = int(minutes * cfg.words_per_minute)
    targets = chapter_targets(total_words, len(outline.chapters))
    wps = cfg.words_per_minute / 60

    scenes: list[Scene] = []
    infos: list[ChapterInfo] = []
    prev_tail = ""
    for idx, target in enumerate(targets):
        draft = get_chapter(topic, client, language, style, outline, idx, target, cfg, run_dir, prev_tail,
                            progress, warnings, facts=research.facts_for(idx) if research else None)
        first = len(scenes) + 1
        ch_words = 0
        for sd in draft.scenes:
            query = " ".join((sd.search_query or "").split()) or outline.chapters[idx].title
            visual = " ".join((sd.visual_description or "").split()) or query
            for piece in split_scene(sd.narration, cfg.max_scene_words):
                n = word_count(piece)
                ch_words += n
                scenes.append(Scene(number=len(scenes) + 1, narration=piece, visual_description=visual,
                                    search_query=query, duration=round(max(n / wps, 1.5), 2)))
        if len(scenes) < first:
            raise LongScriptError(f"Chapter {idx + 1} mein koi scene nahi bana")
        infos.append(ChapterInfo(title=outline.chapters[idx].title, first_scene=first,
                                 last_scene=len(scenes), words=ch_words))
        prev_tail = " ".join(scenes[-1].narration.split()[-30:])

    if len(scenes) > cfg.max_scenes:
        warnings.append(f"{len(scenes)} scenes bane (hadd {cfg.max_scenes}); LONG_MAX_SCENE_WORDS badha kar kam karein")
    board = Storyboard(title=outline.title, hook=outline.hook, language=language, scenes=scenes)
    result = LongScript(storyboard=board, chapters=infos, minutes=minutes,
                        words=sum(i.words for i in infos), warnings=warnings)
    if run_dir:
        (Path(run_dir) / "storyboard.json").write_text(board.model_dump_json(indent=2), encoding="utf-8")
        _save(Path(run_dir) / "long_script.json", result)
    return result
