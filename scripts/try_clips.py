"""Live test: storyboard ke pehle scenes ke liye Pixabay se clips. Asli PIXABAY_API_KEY chahiye."""
import sys
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.models import SceneDraft, ScriptDraft, Storyboard
from app.core.storyboard import build_storyboard
from app.services.pixabay import PixabayError, collect_clips


def load_board() -> Storyboard:
    saved = settings.output_dir / "last_storyboard.json"
    if saved.exists():
        print("Storyboard:", saved)
        return Storyboard.model_validate_json(saved.read_text(encoding="utf-8"))
    print("Saved storyboard nahi mila, sample use ho raha hai.")
    draft = ScriptDraft(
        title="Sample",
        hook="Space is completely silent.",
        scenes=[
            SceneDraft(narration="Space is completely silent.", visual_description="stars", search_query="galaxy stars"),
            SceneDraft(narration="There is no air to carry sound.", visual_description="astronaut", search_query="astronaut space"),
            SceneDraft(narration="Follow for more space facts.", visual_description="earth", search_query="earth from space"),
        ],
    )
    return build_storyboard(draft)


def main() -> None:
    max_scenes = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    settings.ensure_dirs()
    board = load_board()
    out_dir = settings.output_dir / "clips_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(timeout=60) as client:
            clips = collect_clips(board, client, max_scenes=max_scenes)
    except PixabayError as exc:
        print("Pixabay error:", exc)
        sys.exit(1)

    for c in clips:
        size_mb = Path(c.path).stat().st_size / 1_000_000
        shape = "PORTRAIT" if c.portrait else "landscape"
        print(f"scene {c.scene_number}: '{c.query}' -> clip {c.clip_id} | {c.width}x{c.height} {shape} | {c.duration:.0f}s | {size_mb:.1f} MB")
        print("   ", c.page_url)
    portrait = sum(1 for c in clips if c.portrait)
    print(f"Portrait: {portrait}/{len(clips)}")
    (out_dir / "clips.json").write_text(
        "[" + ",".join(c.model_dump_json() for c in clips) + "]", encoding="utf-8"
    )
    print("Saved:", out_dir / "clips.json")


if __name__ == "__main__":
    main()
