"""Topic research: niche se video ideas."""
from app.core.models import TopicIdea, TopicList

SYSTEM_PROMPT = (
    "You are a content strategist for short-form videos (YouTube Shorts, Reels, TikTok). "
    "Suggest specific, curiosity-driven topics that fit a 30 to 45 second video. "
    "Base why_trending on general knowledge of what audiences engage with. "
    "Never invent statistics or claim live trend data."
)


def suggest_topics(niche: str, client, count: int = 5, language: str = "English",
                   trends: list[str] | None = None) -> list[TopicIdea]:
    niche = niche.strip()
    if not niche:
        raise ValueError("Niche khali hai")
    prompt = (
        f"Niche: {niche}\n"
        f"Give {count} different video topic ideas in {language}.\n"
        "- title: a specific topic, not a generic category.\n"
        "- angle: the surprising or useful way to present it.\n"
        "- why_trending: one sentence on why people would watch it."
    )
    if trends:
        prompt += (
            "\n\nCurrently popular videos on YouTube (real data, use only as inspiration for what audiences "
            "are watching now; ignore anything unrelated to the niche; do not copy titles and do not "
            "claim any numbers about them):\n" + "\n".join(f"- {t}" for t in trends[:15])
        )
    result = client.generate_json(prompt, TopicList, system=SYSTEM_PROMPT)
    topics = [t for t in result.topics if t.title.strip()]
    return topics[:count]
