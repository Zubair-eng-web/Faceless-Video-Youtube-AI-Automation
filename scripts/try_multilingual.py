"""Live test: Hindi/Urdu/Arabic ki chhoti video (Gemini aur Pixabay ke baghair, sirf Edge TTS aur FFmpeg).
Chalane ka tareeqa: python -m scripts.try_multilingual   ya   python -m scripts.try_multilingual Hindi"""
import subprocess
import sys

from app.core.config import settings
from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard
from app.services.pixabay import SceneClip
from app.services.quality import check_video
from app.services.thumbnail import ThumbnailError, extract_frame, make_thumbnail
from app.services.tts import TTSError, generate_voiceover
from app.services.video_editor import VideoError, probe_video, render_video

SAMPLES = {
    "Hindi": [
        "\u0928\u092e\u0938\u094d\u0924\u0947 \u0926\u094b\u0938\u094d\u0924\u094b\u0902\u0964",
        "\u0906\u091c \u0905\u0902\u0924\u0930\u093f\u0915\u094d\u0937 \u0915\u0940 \u092c\u093e\u0924 "
        "\u0915\u0930\u0924\u0947 \u0939\u0948\u0902\u0964",
    ],
    "Urdu": [
        "\u0622\u062c \u06c1\u0645 \u062e\u0644\u0627 \u06a9\u06cc \u0628\u0627\u062a "
        "\u06a9\u0631\u062a\u06d2 \u06c1\u06cc\u06ba\u06d4",
        "\u062e\u0644\u0627 \u0628\u06c1\u062a \u062e\u0627\u0645\u0648\u0634 \u06c1\u06d2\u06d4",
    ],
    "Arabic": [
        "\u0645\u0631\u062d\u0628\u0627 \u0628\u0643\u0645.",
        "\u0627\u0644\u064a\u0648\u0645 \u0646\u062a\u062d\u062f\u062b \u0639\u0646 "
        "\u0627\u0644\u0641\u0636\u0627\u0621.",
    ],
}
COLORS = ["0x24415f", "0x5f2a41"]


def make_clip(path, color) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
         f"color=c={color}:s=1080x1920:r=30:d=8", "-c:v", "libx264", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise VideoError(result.stderr.strip()[-300:])


def run_language(language: str) -> bool:
    out_dir = settings.output_dir / "multilingual_test" / language.lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    scenes = [SceneDraft(narration=t, visual_description="test", search_query="test") for t in SAMPLES[language]]
    board = build_storyboard(ScriptDraft(title="Test", hook=SAMPLES[language][0], scenes=scenes), language=language)

    clips = []
    for scene in board.scenes:
        clip_path = out_dir / f"clip_{scene.number}.mp4"
        make_clip(clip_path, COLORS[(scene.number - 1) % len(COLORS)])
        clips.append(SceneClip(scene_number=scene.number, clip_id=scene.number, path=str(clip_path), query="test",
                               width=1080, height=1920, duration=8, portrait=True, page_url=""))

    vo = generate_voiceover(board, out_dir / "audio")
    video = render_video(board, clips, vo, out_dir)
    report = check_video(video, vo, board, clips, out_dir / "captions.ass")

    frame = extract_frame(out_dir / "segments" / "seg_01.mp4", 1.0, out_dir / "thumb_frame.jpg")
    thumb = make_thumbnail(frame, " ".join(SAMPLES[language][0].split()[:3]), out_dir / "thumbnail.jpg",
                           font_path=settings.fonts_dir / "arialbd.ttf")

    spoken = len(board.full_narration.split())
    print(f"{language}: voice {vo.voice} | duration {vo.duration:.1f}s | words {len(vo.words)} (text me {spoken})")
    print(f"{language}: video {probe_video(video)['width']}x{probe_video(video)['height']} -> {video}")
    print(f"{language}: thumbnail -> {thumb}")
    for issue in report.issues:
        print(f"   [{issue.level.upper()}] {issue.code}: {issue.message}")
    print(f"{language}: QUALITY {'PASS' if report.passed else 'FAIL'}")
    return report.passed


def main() -> None:
    settings.ensure_dirs()
    languages = sys.argv[1:] or list(SAMPLES)
    failed = 0
    for language in languages:
        if language not in SAMPLES:
            print(f"'{language}' ka sample nahi. Maujood: {', '.join(SAMPLES)}")
            failed += 1
            continue
        try:
            if not run_language(language):
                failed += 1
        except (TTSError, VideoError, ThumbnailError, ValueError) as exc:
            failed += 1
            print(f"{language}: ERROR {exc}")
        print()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
