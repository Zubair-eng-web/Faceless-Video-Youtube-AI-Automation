"""Fonts aur FFmpeg ki jaanch, aur Hindi/Urdu/Arabic ke caption aur thumbnail ke sample images."""
import subprocess
import sys
from pathlib import Path

from PIL import features

from app.core.config import settings
from app.services.captions import build_ass
from app.services.fonts import LANGUAGE_FONTS, caption_style, installed_families
from app.services.thumbnail import ThumbnailError, make_thumbnail
from app.services.tts import WordTiming
from app.services.video_editor import prepare_fonts

SAMPLES = {
    "Hindi": "\u0928\u092e\u0938\u094d\u0924\u0947 \u0926\u094b\u0938\u094d\u0924\u094b\u0902\u0964 "
             "\u0906\u091c \u0905\u0902\u0924\u0930\u093f\u0915\u094d\u0937 \u0915\u0940 "
             "\u092c\u093e\u0924 \u0915\u0930\u0924\u0947 \u0939\u0948\u0902\u0964",
    "Urdu": "\u0622\u062c \u06c1\u0645 \u062e\u0644\u0627 \u06a9\u06cc \u0628\u0627\u062a "
            "\u06a9\u0631\u062a\u06d2 \u06c1\u06cc\u06ba\u06d4",
    "Arabic": "\u0645\u0631\u062d\u0628\u0627 \u0628\u0643\u0645. \u0627\u0644\u064a\u0648\u0645 "
              "\u0646\u062a\u062d\u062f\u062b \u0639\u0646 \u0627\u0644\u0641\u0636\u0627\u0621.",
}


def run_ffmpeg(args, cwd=None) -> None:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-300:])


def ffmpeg_features() -> dict:
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return {name: f"--enable-{name}" in result.stdout for name in ("libass", "libharfbuzz", "libfribidi")}


def caption_sample(language: str, text: str, out_dir: Path) -> Path:
    work = out_dir / language.lower()
    work.mkdir(parents=True, exist_ok=True)
    words = [WordTiming(text=w, start=round(i * 0.5, 2), end=round(i * 0.5 + 0.5, 2))
             for i, w in enumerate(text.split())]
    (work / "captions.ass").write_text(build_ass(words, **caption_style(language)), encoding="utf-8")
    has_fonts = prepare_fonts(settings.fonts_dir, work)
    flt = "ass=captions.ass" + (":fontsdir=fonts" if has_fonts else "")
    out = (work / "caption_sample.png").resolve()
    run_ffmpeg(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                "color=c=0x1b2a3a:s=1080x1920:d=1:r=30", "-vf", flt, "-frames:v", "1", str(out)], cwd=work)
    return out


def thumbnail_sample(language: str, text: str, out_dir: Path) -> Path:
    work = out_dir / language.lower()
    background = (work / "bg.jpg").resolve()
    run_ffmpeg(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                "color=c=0x2a4a6a:s=1280x720", "-frames:v", "1", str(background)])
    short = " ".join(text.split()[:3])
    return make_thumbnail(background, short, work / "thumbnail_sample.jpg",
                          font_path=settings.fonts_dir / "arialbd.ttf")


def main() -> None:
    problems = 0
    print("Pillow raqm (sirf maloomat):", features.check("raqm"))

    found = ffmpeg_features()
    if not found:
        print("FFmpeg nahi mila (PATH me ffmpeg hona chahiye).")
        sys.exit(1)
    for name, ok in found.items():
        print(f"FFmpeg {name}: {'OK' if ok else 'NAHI MILA'}")
    if not (found.get("libass") and found.get("libharfbuzz") and found.get("libfribidi")):
        problems += 1
        print("WARNING: Hindi/Urdu/Arabic ke huroof sahi jurre nahi dikhenge. FFmpeg ka full build chahiye.")

    have = installed_families(settings.fonts_dir)
    print("Maujood font families:", ", ".join(sorted(have)) or "koi nahi")
    for language, candidates in LANGUAGE_FONTS.items():
        chosen = caption_style(language)["font"]
        status = "OK" if chosen in have else "NAHI MILA (FFmpeg ka apna fallback chalega)"
        print(f"{language}: font '{chosen}' -> {status}")
        if chosen not in have:
            problems += 1

    out_dir = settings.output_dir / "fonts_test"
    for language, text in SAMPLES.items():
        try:
            caption = caption_sample(language, text, out_dir)
            thumb = thumbnail_sample(language, text, out_dir)
            print(f"{language}: caption sample -> {caption}")
            print(f"{language}: thumbnail      -> {thumb}")
        except (RuntimeError, ThumbnailError) as exc:
            problems += 1
            print(f"{language}: ERROR {exc}")

    print()
    print("Ab in images ko khol kar dekhein (neeche ki hidayat dekhein).")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
