"""Live test: storyboard -> voiceover + clips -> pehli poori video. Asli PIXABAY key aur internet chahiye."""
import sys

import httpx

from app.core.config import settings
from app.core.models import Storyboard
from app.services.pixabay import PixabayError, collect_clips
from app.services.tts import TTSError, generate_voiceover
from app.services.video_editor import VideoError, probe_video, render_video


def main() -> None:
    settings.ensure_dirs()
    saved = settings.output_dir / "last_storyboard.json"
    if not saved.exists():
        print("Pehle 'python -m scripts.try_script' chalayen (storyboard chahiye).")
        sys.exit(1)
    board = Storyboard.model_validate_json(saved.read_text(encoding="utf-8"))
    out_dir = settings.output_dir / "video_test"
    try:
        print("1/3 Voiceover ban rahi hai...")
        vo = generate_voiceover(board, out_dir / "audio")
        print("2/3 Clips download ho rahe hain...")
        with httpx.Client(timeout=60) as client:
            clips = collect_clips(board, client)
        portrait = sum(1 for c in clips if c.portrait)
        print(f"    {len(clips)} clips, portrait: {portrait}/{len(clips)}")
        print("3/3 Video render ho rahi hai (1-2 minute lag sakte hain)...")
        video = render_video(board, clips, vo, out_dir)
    except (TTSError, PixabayError, VideoError, ValueError) as exc:
        print("Error:", exc)
        sys.exit(1)

    (out_dir / "voiceover.json").write_text(vo.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "clips.json").write_text("[" + ",".join(c.model_dump_json() for c in clips) + "]", encoding="utf-8")
    info = probe_video(video)
    size_mb = video.stat().st_size / 1_000_000
    print()
    print("Video   :", video)
    print(f"Size    : {info['width']}x{info['height']}")
    print(f"Duration: {info['duration']:.1f}s (voiceover: {vo.duration:.1f}s)")
    print(f"File    : {size_mb:.1f} MB")
    from app.services.music import list_tracks
    _tracks = list_tracks(settings.music_dir)
    _count = sum(len(v) for v in _tracks.values())
    print("Music   :", f"{_count} track(s) mile, moods: {', '.join(sorted(_tracks))}" if _count else "nahi mili (assets/music khali hai)")


if __name__ == "__main__":
    main()
