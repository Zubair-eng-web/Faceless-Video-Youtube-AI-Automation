"""Thumbnail: video ke frame par bara text laga kar JPEG banana."""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.core.config import settings
from app.services.fonts import needs_complex_layout
from app.services.thumbnail_ass import render_complex_thumbnail

MAX_BYTES = 2_000_000  # YouTube thumbnail ki limit 2 MB
MAX_LINES = 4


class ThumbnailError(RuntimeError):
    pass


def extract_frame(video_path, at_seconds: float, out_path, runner=subprocess.run) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = runner(
        ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-ss", f"{at_seconds:.2f}",
         "-i", str(video_path), "-frames:v", "1", "-q:v", "2", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise ThumbnailError(f"Frame nahi nikla: {(result.stderr or '').strip()[-300:]}")
    return out


def load_font(font_path, size: int):
    if font_path and Path(font_path).exists():
        try:
            return ImageFont.truetype(str(font_path), size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except TypeError:  # bohat purani Pillow
        return ImageFont.load_default()


def wrap_text(text: str, font, max_width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and font.getlength(trial) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def fit_text(text: str, font_path, max_width: int, max_height: int,
             start_size: int = 170, min_size: int = 56, step: int = 6):
    """Font ka size utna ghatana jab tak text 4 lines aur diye gaye height me aa jaye."""
    size = start_size
    while True:
        font = load_font(font_path, size)
        lines = wrap_text(text, font, max_width)
        height = len(lines) * int(size * 1.2)
        if (len(lines) <= MAX_LINES and height <= max_height) or size <= min_size:
            return font, lines, size
        size -= step


def make_thumbnail(frame_path, text: str, out_path, font_path=None, size=(1080, 1920)) -> Path:
    text = " ".join(text.split()).upper()
    if not text:
        raise ThumbnailError("Thumbnail ka text khali hai")
    if needs_complex_layout(text):  # Hindi/Urdu/Arabic: Pillow sahi shaping nahi karta, libass se banate hain
        fonts_dir = Path(font_path).parent if font_path else settings.fonts_dir
        return render_complex_thumbnail(frame_path, text, out_path, fonts_dir, size=size)
    width, height = size
    img = Image.open(frame_path).convert("RGB")
    img = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
    img = Image.blend(img, Image.new("RGB", size, (0, 0, 0)), 0.35)  # text saaf parhne ke liye halka andhera

    font, lines, font_size = fit_text(text, font_path, int(width * 0.86), int(height * 0.40))
    line_height = int(font_size * 1.2)
    y = (height - line_height * len(lines)) // 2
    stroke = max(4, font_size // 12)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        x = (width - font.getlength(line)) / 2
        fill = (255, 221, 0) if i == len(lines) - 1 else (255, 255, 255)  # aakhri line peeli
        draw.text((x, y + i * line_height), line, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=(0, 0, 0))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    quality = 92
    while True:
        img.save(out, "JPEG", quality=quality, optimize=True)
        if out.stat().st_size <= MAX_BYTES or quality <= 60:
            break
        quality -= 8
    return out
