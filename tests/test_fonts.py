from app.services import fonts
from app.services.fonts import (
    caption_style,
    font_for_language,
    font_for_text,
    installed_families,
    is_rtl,
    needs_complex_layout,
    script_hint,
)

HINDI = "\u0928\u092e\u0938\u094d\u0924\u0947"
URDU = "\u0622\u062c \u06c1\u0645 \u062e\u0644\u0627"
ARABIC = "\u0645\u0631\u062d\u0628\u0627"


def test_latin_languages_use_arial_and_uppercase(tmp_path):
    for language in ("English", "spanish", "French"):
        assert caption_style(language, tmp_path) == {"font": "Arial", "font_size": 78, "uppercase": True}


def test_hindi_style_has_no_uppercase_and_bigger_font(tmp_path):
    assert caption_style("Hindi", tmp_path) == {"font": "Noto Sans Devanagari", "font_size": 84, "uppercase": False}


def test_font_uses_installed_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(fonts, "installed_families", lambda folder: {"Nirmala UI"})
    assert font_for_language("Hindi", tmp_path) == "Nirmala UI"


def test_noto_is_preferred_when_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(fonts, "installed_families", lambda folder: {"Nirmala UI", "Noto Sans Devanagari"})
    assert font_for_language("hindi", tmp_path) == "Noto Sans Devanagari"


def test_rtl_languages():
    assert is_rtl("Urdu") and is_rtl("arabic")
    assert not is_rtl("Hindi") and not is_rtl("English")


def test_script_hint():
    assert "Devanagari" in script_hint("Hindi")
    assert "Roman Urdu" in script_hint("Urdu")
    assert script_hint("English") == ""


def test_needs_complex_layout():
    assert needs_complex_layout(HINDI) and needs_complex_layout(URDU) and needs_complex_layout(ARABIC)
    assert needs_complex_layout("Hello " + HINDI)
    assert not needs_complex_layout("Hello world 123")


def test_font_for_text_follows_script(monkeypatch, tmp_path):
    monkeypatch.setattr(fonts, "installed_families", lambda folder: set())
    assert font_for_text(HINDI, tmp_path) == "Noto Sans Devanagari"
    assert font_for_text(ARABIC, tmp_path) == "Noto Naskh Arabic"
    assert font_for_text("Hello", tmp_path) == "Arial"


def test_installed_families_ignores_missing_dir_and_broken_fonts(tmp_path):
    assert installed_families(tmp_path / "nope") == set()
    (tmp_path / "broken.ttf").write_bytes(b"not a font")
    assert installed_families(tmp_path) == set()
