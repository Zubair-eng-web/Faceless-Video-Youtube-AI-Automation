"""Live test: niche -> topics -> script -> storyboard. 2 Gemini requests lagti hain."""
import sys

from app.agents.research_agent import suggest_topics
from app.agents.script_agent import generate_script
from app.core.config import settings
from app.services.gemini_client import GeminiClient, GeminiError


def main() -> None:
    niche = sys.argv[1] if len(sys.argv) > 1 else "space facts"
    settings.ensure_dirs()
    try:
        client = GeminiClient()
        print("Model:", client.model)
        print("Niche:", niche)
        print()
        topics = suggest_topics(niche, client, count=3)
        if not topics:
            print("Koi topic nahi aaya.")
            sys.exit(1)
        for i, t in enumerate(topics, 1):
            print(f"{i}. {t.title} -- {t.angle}")
        print()
        board = generate_script(topics[0].title, client)
    except GeminiError as exc:
        print("Gemini error:", exc)
        sys.exit(1)

    print("TITLE:", board.title)
    print("HOOK :", board.hook)
    for s in board.scenes:
        print(f"[{s.number}] {s.duration}s | {s.search_query}")
        print("    ", s.narration)
    print("TOTAL:", board.total_duration, "seconds")

    out = settings.output_dir / "last_storyboard.json"
    out.write_text(board.model_dump_json(indent=2), encoding="utf-8")
    print("Saved:", out)


if __name__ == "__main__":
    main()
