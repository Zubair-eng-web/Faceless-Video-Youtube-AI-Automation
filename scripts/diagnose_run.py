"""Ek run ka tajziya: har scene ka waqt, awaaz ki khamoshi, kala screen aur clip. Kuch badalta nahi.
Chalane ka tareeqa: python -m scripts.diagnose_run [run folder]   (folder na den to sab se naya run)"""
import json
import sys
from pathlib import Path

from app.core.config import settings
from app.services.quality import analyze_media, parse_black_segments, parse_silences
from app.services.thumbnail import ThumbnailError, extract_frame
from app.services.video_editor import detect_leading_black


def latest_run():
    results = sorted((settings.output_dir / "runs").glob("*/result.json"), key=lambda p: p.stat().st_mtime)
    return results[-1].parent if results else None


def scene_at(t, scenes):
    for scene in scenes:
        if scene["start_offset"] <= t < scene["start_offset"] + scene["duration"]:
            return scene["number"]
    return None


def main() -> None:
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_run()
    if run is None or not (run / "voiceover.json").exists():
        print("Run folder nahi mila ya us me voiceover.json nahi hai.")
        sys.exit(1)
    vo = json.loads((run / "voiceover.json").read_text(encoding="utf-8"))
    clips = {c["scene_number"]: c for c in json.loads((run / "clips.json").read_text(encoding="utf-8"))}

    print("Run:", run)
    print(f"Voiceover: {vo['voice']} | {vo['duration']:.1f}s")
    print()
    print("scene |  shuru | lambai | bolna shuru | bolna khatam | aakhir ki khamoshi | clip (kala shuru) | query")
    total_tail = 0.0
    for s in vo["scenes"]:
        words = s["words"]
        lead = words[0]["start"] if words else 0.0
        end = words[-1]["end"] if words else s["duration"]
        tail = s["duration"] - end
        total_tail += tail
        clip = clips.get(s["number"])
        black = detect_leading_black(clip["path"]) if clip and Path(clip["path"]).exists() else 0.0
        clip_text = f"{clip['clip_id']} ({black:.2f}s)" if clip else "-"
        query = clip["query"] if clip else "-"
        print(f"{s['number']:>5} | {s['start_offset']:6.1f} | {s['duration']:6.1f} | {lead:11.2f} | "
              f"{end:12.2f} | {tail:18.2f} | {clip_text} | {query}")
    print()
    print(f"Scenes ke aakhir ki kul khamoshi: {total_tail:.1f}s")

    video = run / "video.mp4"
    if not video.exists():
        return
    try:
        log = analyze_media(video)
    except Exception as exc:
        print("Video ki jaanch fail:", exc)
        return
    blacks = [(a, b) for a, b in parse_black_segments(log) if b - a >= 0.5]
    silences = [(a, d) for a, d in parse_silences(log, vo["duration"]) if d >= 1.5]

    print(f"Kala screen (0.5s se zyada): {len(blacks)}")
    for i, (a, b) in enumerate(blacks, 1):
        scene = scene_at(a, vo["scenes"])
        clip = clips.get(scene)
        clip_id = clip["clip_id"] if clip else "-"
        try:
            frame = extract_frame(video, (a + b) / 2, run / "diag" / f"black_{i}.jpg")
        except ThumbnailError:
            frame = "frame nahi nikla"
        print(f"  {a:.1f}s - {b:.1f}s | scene {scene} | clip {clip_id} | frame: {frame}")
    print(f"Lambi khamoshi (1.5s se zyada): {len(silences)}")
    for a, d in silences:
        print(f"  {a:.1f}s par {d:.1f}s | scene {scene_at(a, vo['scenes'])}")


if __name__ == "__main__":
    main()
