"""ScriptDraft ko numbered scenes aur durations wale Storyboard me badalna."""
from app.core.models import Scene, ScriptDraft, Storyboard

WORDS_PER_SECOND = 2.5
MIN_SCENE_SECONDS = 2.0


def estimate_duration(text: str) -> float:
    """Bolne ka andaza. Asli duration baad me voiceover se milegi."""
    words = len(text.split())
    return round(max(words / WORDS_PER_SECOND, MIN_SCENE_SECONDS), 1)


def build_storyboard(draft: ScriptDraft, language: str = "English") -> Storyboard:
    scenes: list[Scene] = []
    for item in draft.scenes:
        narration = " ".join(item.narration.split())
        if not narration:
            continue
        query = " ".join(item.search_query.split()) or draft.title.strip()
        scenes.append(
            Scene(
                number=len(scenes) + 1,
                narration=narration,
                visual_description=" ".join(item.visual_description.split()),
                search_query=query,
                duration=estimate_duration(narration),
            )
        )
    if not scenes:
        raise ValueError("Script me koi scene nahi mila")
    return Storyboard(
        title=draft.title.strip(),
        hook=draft.hook.strip(),
        language=language,
        scenes=scenes,
    )
