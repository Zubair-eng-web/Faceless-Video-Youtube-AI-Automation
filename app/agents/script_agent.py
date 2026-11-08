"""Script + storyboard: topic se scenes aur stock-video search queries."""
from app.core.models import ScriptDraft, Storyboard
from app.core.storyboard import WORDS_PER_SECOND, build_storyboard
from app.services.fonts import script_hint

SYSTEM_PROMPT = (
    "You write scripts for faceless short-form videos (YouTube Shorts, Reels, TikTok). "
    "The voiceover is read by a text-to-speech voice, so write plain spoken sentences: "
    "no emojis, no hashtags, no stage directions, no scene labels. "
    "Never invent statistics, quotes or sources; if you are not sure of a fact, leave it out. "
    "Every scene needs a search_query for a stock footage site: 2 to 4 English words describing "
    "something concrete and filmable (for example 'ocean waves sunset'), never abstract ideas, "
    "people's names or brand names."
)


def generate_script(topic: str, client, language: str = "English", target_seconds: int = 40) -> Storyboard:
    topic = topic.strip()
    if not topic:
        raise ValueError("Topic khali hai")
    words = round(target_seconds * WORDS_PER_SECOND)
    base = round(target_seconds / 5)
    min_scenes = max(3, base - 1)
    max_scenes = base + 1
    prompt = (
        f"Topic: {topic}\n"
        f"Narration language: {language}{script_hint(language)}\n"
        f"Total narration length: at most {words} words (about {target_seconds} seconds). Do not go over.\n"
        f"Split it into {min_scenes} to {max_scenes} scenes.\n"
        "Rules:\n"
        "- Scene 1 is the hook: one strong sentence of at most 12 words that makes people keep watching.\n"
        "- The last scene ends with a short call to follow or comment.\n"
        "- narration: what the voice says, in the narration language.\n"
        "- visual_description: one sentence on what the viewer sees.\n"
        "- search_query: always in English, even if the narration is not.\n"
        "- title: a short catchy video title.\n"
        "- hook: the same text as the scene 1 narration."
    )
    draft = client.generate_json(prompt, ScriptDraft, system=SYSTEM_PROMPT)
    return build_storyboard(draft, language=language)
