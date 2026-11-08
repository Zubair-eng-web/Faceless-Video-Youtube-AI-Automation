"""Live test: storyboard -> voiceover + word timings. Internet chahiye, key nahi."""
import sys

from app.core.config import settings
from app.core.models import SceneDraft, ScriptDraft, Storyboard
from app.core.storyboard import build_storyboard
from app.services.tts import TTSError, apply_durations, generate_voiceover


def load_board() -> Storyboard:
    saved = settings.output_dir / "last_storyboard.json"
    if saved.exists():
        print("Storyboard:", saved)
        return Storyboard.model_validate_json(saved.read_text(encoding="utf-8"))
    print("Saved storyboard nahi mila, sample use ho raha hai.")
    draft = ScriptDraft(
        title="Sample",
        hook="Did you know space is completely silent?",
        scenes=[
            SceneDraft(narration="Did you know space is completely silent?", visual_description="stars", search_query="galaxy stars"),
            SceneDraft(narration="There is no air, so sound has nothing to travel through.", visual_description="astronaut", search_query="astronaut space"),
            SceneDraft(narration="Follow for more space facts.", visual_description="earth", search_query="earth from space"),
        ],
    )
    return build_storyboard(draft)


def main() -> None:
    settings.ensure_dirs()
    board = load_board()
    out_dir = settings.output_dir / "voice_test"
    try:
        vo = generate_voiceover(board, out_dir)
    except (TTSError, ValueError) as exc:
        print("Voiceover error:", exc)
        sys.exit(1)

    print("Voice   :", vo.voice)
    print("Duration:", vo.duration, "seconds")
    for s in vo.scenes:
        print(f"  scene {s.number}: {s.duration}s, {len(s.words)} words, starts at {s.start_offset}s")
    print("Pehle 8 words:")
    for w in vo.words[:8]:
        print(f"  {w.start:6.2f} -> {w.end:6.2f}  {w.text}")

    (out_dir / "voiceover.json").write_text(vo.model_dump_json(indent=2), encoding="utf-8")
    updated = apply_durations(board, vo)
    print("Estimated total:", board.total_duration, "s | Asli total:", updated.total_duration, "s")
    print("Audio:", vo.path)


if __name__ == "__main__":
    main()
