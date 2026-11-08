"""AI recommendations: published videos ke numbers se agli videos ke liye mashwara."""
from pydantic import BaseModel

from app.services.gemini_client import GeminiClient

MIN_VIDEOS = 3
MAX_ROWS = 30

SYSTEM_PROMPT = (
    "You are a YouTube Shorts growth analyst. Use only the numbers you are given and never invent "
    "metrics. Be specific and practical."
)


class Insights(BaseModel):
    summary: str
    what_works: list[str]
    what_to_improve: list[str]
    next_topics: list[str]


def format_rows(videos: list[dict]) -> str:
    lines = ["title | topic | views | likes | comments"]
    for v in videos[:MAX_ROWS]:
        lines.append(
            f"{v.get('title') or '-'} | {v.get('topic') or '-'} | {v['views']} | {v.get('likes') or 0} | {v.get('comments') or 0}"
        )
    return "\n".join(lines)


def generate_insights(videos: list[dict], client) -> Insights:
    rows = [v for v in videos if v.get("views") is not None]
    if len(rows) < MIN_VIDEOS:
        raise ValueError(f"Kam az kam {MIN_VIDEOS} videos ke stats chahiye (abhi {len(rows)}). Pehle 'Stats refresh karein' dabayen.")
    prompt = (
        "Here are the performance numbers of my published short videos (newest first):\n"
        f"{format_rows(rows)}\n\n"
        "Analyze them and answer in English:\n"
        "- summary: 2 to 3 sentences on overall performance.\n"
        "- what_works: 2 to 4 patterns in the better videos (topic type, title style).\n"
        "- what_to_improve: 2 to 4 concrete changes for the next videos (hook, title, topic choice).\n"
        "- next_topics: 5 specific video topic ideas based on what performs.\n"
        "If total views are very low (for example private or brand-new videos), say the data is too thin "
        "to judge and keep the advice general."
    )
    return client.generate_json(prompt, Insights, system=SYSTEM_PROMPT)


def insights_from_videos(videos: list[dict]) -> dict:
    return generate_insights(videos, GeminiClient()).model_dump()
