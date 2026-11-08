"""Render existing long-form narration and clips as a 16:9 video.
Usage: python -m scripts.try_long_render [--scenes 10] [run folder]
Use --scenes 0 to render all scenes. FFmpeg must be installed."""
import argparse
import json
from pathlib import Path

from app.services.long_render import render_long_video
from app.services.long_script import LongScript
from app.services.pixabay import SceneClip
from app.services.tts import Voiceover

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("run", nargs="?", default=str(root / "output" / "long_test" / "how_black_holes_form_5min"))
parser.add_argument("--scenes", type=int, default=10, help="Scenes to render; 0 = all.")
parser.add_argument("--chunk-scenes", type=int, default=20)
parser.add_argument("--no-music", action="store_true")
parser.add_argument("--no-sfx", action="store_true")
args = parser.parse_args()
if args.scenes < 0:
    parser.error("--scenes must be 0 or a positive number")
if args.chunk_scenes < 1:
    parser.error("--chunk-scenes must be at least 1")

run = Path(args.run)
paths = (run / "long_script.json", run / "clips.json", run / "narration" / "voiceover.json")
for p in paths:
    if not p.is_file():
        raise SystemExit(f"[FAIL] Missing {p}. Generate the script, voiceover, and clips first.")

script = LongScript.model_validate_json(paths[0].read_text(encoding="utf-8"))
all_scenes = script.storyboard.scenes
count = len(all_scenes) if args.scenes == 0 else min(args.scenes, len(all_scenes))
if count == 0:
    raise SystemExit("[FAIL] The script has no scenes.")
board = script.storyboard.model_copy(update={"scenes": all_scenes[:count]})
nums = {s.number for s in board.scenes}

data = json.loads(paths[1].read_text(encoding="utf-8"))
items = list(data.values()) if isinstance(data, dict) else data
clips = [c for c in (SceneClip.model_validate(i) for i in items) if c.scene_number in nums]

voiceover = Voiceover.model_validate_json(paths[2].read_text(encoding="utf-8"))
voice_scenes = [s for s in voiceover.scenes if s.number in nums]
miss_v = nums - {s.number for s in voice_scenes}
miss_c = nums - {c.scene_number for c in clips}
if miss_v:
    raise SystemExit(f"[FAIL] Voiceover missing scenes {sorted(miss_v)}. Run try_long_voice with more --scenes.")
if miss_c:
    raise SystemExit(f"[FAIL] Clips missing scenes {sorted(miss_c)}. Run try_long_clips with more --scenes.")
voiceover = voiceover.model_copy(update={"scenes": voice_scenes})

chapter_ends = [i for i, s in enumerate(board.scenes[:-1], start=1)
                if any(c.last_scene == s.number for c in script.chapters)]
out_dir = run / "render"
no_music = out_dir / "no_music"
if args.no_music:
    no_music.mkdir(parents=True, exist_ok=True)

video = render_long_video(board, clips, voiceover, out_dir, chapter_ends=chapter_ends,
                          sfx=not args.no_sfx, max_chunk_scenes=args.chunk_scenes,
                          music_dir=str(no_music) if args.no_music else None)
rp = out_dir / "render_report.json"
r = json.loads(rp.read_text(encoding="utf-8"))
print(f"\nVideo   : {video}")
print(f"Scenes  : {count}/{len(all_scenes)}")
print(f"Format  : {r['width']}x{r['height']}")
print(f"Duration: {r['actual_seconds']:.1f}s (expected {r['expected_seconds']:.1f}s, drift {r['drift_seconds']:+.2f}s)")
print(f"Chunks  : {r['chunks']} (abhi bane: {r['chunks_rendered_now']})")
print(f"Rendered: {r['render_seconds']:.1f}s")
print(f"Report  : {rp}")
