"""Hindi/Urdu/Arabic ka thumbnail: text FFmpeg ke ass filter (libass) se lagta hai, jo sahi shaping karta hai."""
import subprocess
from pathlib import Path

from app.services.fonts import font_for_text
from app.services.video_editor import prepare_fonts

MAX_BYTES = 2_000_000
QUALITIES = (3, 6, 10)


def pick_font_size(text: str) -> int:
    n = len(text)
    if n <= 12:
        return 150
    if n <= 24:
        return 124
    if n <= 40:
        return 104
    return 88


def _esc(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\\", "").replace("\n", " ").strip()


def build_thumbnail_ass(text: str, font: str, width: int = 1080, height: int = 1920) -> str:
    size = pick_font_size(text)
    outline = max(6, size // 10)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{size},&H0000DDFF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{outline},2,5,90,90,60,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 0,0:00:00.00,0:00:10.00,Default,,0,0,0,,{{\\an5}}{_esc(text)}",
    ]
    return "\n".join(lines) + "\n"


def render_complex_thumbnail(frame_path, text: str, out_path, fonts_dir, size=(1080, 1920),
                             runner=subprocess.run) -> Path:
    from app.services.thumbnail import ThumbnailError  # circular import se bachne ke liye yahin

    width, height = size
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / "thumb_ass"
    work.mkdir(parents=True, exist_ok=True)
    has_fonts = prepare_fonts(fonts_dir, work)
    font = font_for_text(text, fonts_dir)
    (work / "thumb.ass").write_text(build_thumbnail_ass(text, font, width, height), encoding="utf-8")
    ass = "ass=thumb.ass" + (":fontsdir=fonts" if has_fonts else "")
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
          f"eq=brightness=-0.18,{ass}")
    for quality in QUALITIES:
        result = runner(
            ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(Path(frame_path).resolve()),
             "-vf", vf, "-frames:v", "1", "-q:v", str(quality), str(out)],
            cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            raise ThumbnailError(f"Thumbnail render fail: {(result.stderr or '').strip()[-300:]}")
        if out.stat().st_size <= MAX_BYTES:
            return out
    return out
