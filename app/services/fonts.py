"""Language ke hisab se caption ka font, script ki pehchan aur font ki jaanch."""
import re
from pathlib import Path

from PIL import ImageFont

from app.core.config import settings

LATIN_FONT = "Arial"
DEFAULT_FONT_SIZE = 78

# Har language ke font families, behtareen pehle. assets/fonts me jo pehla mile wahi use hota hai.
LANGUAGE_FONTS = {
    "Hindi": ["Noto Sans Devanagari", "Nirmala UI"],
    "Urdu": ["Noto Naskh Arabic", "Arial"],
    "Arabic": ["Noto Naskh Arabic", "Arial"],
}
FONT_SIZES = {"Hindi": 84, "Urdu": 88, "Arabic": 88}
RTL_LANGUAGES = {"Urdu", "Arabic"}
SCRIPT_HINTS = {
    "Hindi": " (write it in Devanagari script, not in Roman letters)",
    "Urdu": " (write it in Urdu script using Arabic letters, not Roman Urdu)",
    "Arabic": " (write it in Modern Standard Arabic using Arabic script)",
}

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def normalize_language(language: str) -> str:
    return language.strip().title()


def is_latin_language(language: str) -> bool:
    return normalize_language(language) not in LANGUAGE_FONTS


def is_rtl(language: str) -> bool:
    return normalize_language(language) in RTL_LANGUAGES


def script_hint(language: str) -> str:
    return SCRIPT_HINTS.get(normalize_language(language), "")


def installed_families(fonts_dir) -> set:
    """assets/fonts ki fonts ke family names."""
    families = set()
    folder = Path(fonts_dir)
    if not folder.is_dir():
        return families
    for path in folder.iterdir():
        if path.suffix.lower() in (".ttf", ".otf", ".ttc"):
            try:
                families.add(ImageFont.truetype(str(path), 20).getname()[0])
            except Exception:
                continue
    return families


def font_for_language(language: str, fonts_dir=None) -> str:
    candidates = LANGUAGE_FONTS.get(normalize_language(language))
    if not candidates:
        return LATIN_FONT
    have = installed_families(fonts_dir or settings.fonts_dir)
    for family in candidates:
        if family in have:
            return family
    return candidates[0]


def caption_style(language: str, fonts_dir=None) -> dict:
    """build_ass ke liye font, size aur uppercase ki setting."""
    return {
        "font": font_for_language(language, fonts_dir),
        "font_size": FONT_SIZES.get(normalize_language(language), DEFAULT_FONT_SIZE),
        "uppercase": is_latin_language(language),
    }


def needs_complex_layout(text: str) -> bool:
    """Devanagari ya Arabic script wala text (Pillow ke bajaye libass se render hota hai)."""
    return bool(DEVANAGARI_RE.search(text) or ARABIC_RE.search(text))


def font_for_text(text: str, fonts_dir=None) -> str:
    if DEVANAGARI_RE.search(text):
        return font_for_language("Hindi", fonts_dir)
    if ARABIC_RE.search(text):
        return font_for_language("Arabic", fonts_dir)
    return LATIN_FONT
