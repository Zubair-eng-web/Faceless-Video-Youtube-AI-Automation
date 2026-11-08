"""Asli runner: Gemini + Pixabay + FFmpeg se poori video (API ke background job ke liye)."""
import httpx

from app.agents.research_agent import suggest_topics
from app.services.trends import trend_titles
from app.pipeline import PipelineResult, run_pipeline
from app.services.gemini_client import GeminiClient


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def pick_topic(topics, used) -> str:
    """Pehla aisa topic jo is channel par pehle na bana ho. Sab bane hue hon to pehla."""
    if not topics:
        raise ValueError("Koi topic nahi aaya")
    seen = {_norm(u) for u in used}
    for topic in topics:
        if _norm(topic.title) not in seen:
            return topic.title
    return topics[0].title


def default_runner(topic, niche, language, seconds, voice, used_topics, branding=None) -> PipelineResult:
    gemini = GeminiClient()
    if not topic:
        trends = trend_titles(niche, language)
        print(f"Trends: {len(trends)} popular titles mile" if trends else "Trends: nahi mile (normal research)", flush=True)
        topic = pick_topic(
            suggest_topics(niche, gemini, count=5, language=language, **({"trends": trends} if trends else {})),
            used_topics)
    with httpx.Client(timeout=60) as http:
        return run_pipeline(
            topic, gemini, http,
            language=language, target_seconds=seconds, voice=voice,
            **({"branding": branding} if branding else {}),
            progress=lambda message: print(message, flush=True),
        )
