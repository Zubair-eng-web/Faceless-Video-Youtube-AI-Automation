import pytest

from app.services.branding import (Branding, ass_style_color, ass_tag_color, logo_overlay_filters,
                                   normalize_hex, resolve_file)


def test_normalize_hex():
    assert normalize_hex("ffcc00") == "#FFCC00"
    assert normalize_hex(" #ffcc00 ") == "#FFCC00"
    for bad in ("", "#FFF", "red", "#GGGGGG"):
        with pytest.raises(ValueError):
            normalize_hex(bad)


def test_ass_colors_are_bgr():
    assert ass_style_color("#FF0000") == "&H000000FF"
    assert ass_tag_color("#FFFF00") == "{\\c&H00FFFF&}"   # purana peela rang
    assert ass_tag_color("#FFFFFF") == "{\\c&HFFFFFF&}"   # purana safed rang


def test_branding_defaults_match_old_look():
    b = Branding()
    assert ass_tag_color(b.highlight_color) == "{\\c&H00FFFF&}"
    assert b.logo_path is None and b.font_scale == 1.0


def test_branding_validation():
    with pytest.raises(ValueError):
        Branding(highlight_color="nahi")
    with pytest.raises(ValueError):
        Branding(logo_position="upar")
    with pytest.raises(ValueError):
        Branding(font_scale=5)
    assert Branding(highlight_color="00ff00").highlight_color == "#00FF00"


def test_logo_filters_positions():
    p = logo_overlay_filters("v", 3, "vb", 1080, "top-right", 0.5, 0.2)
    assert p[0] == "[3:v]scale=216:-1,format=rgba,colorchannelmixer=aa=0.50[logo]"
    assert p[1] == "[v][logo]overlay=W-w-40:40[vb]"
    assert "overlay=40:H-h-40" in logo_overlay_filters("v", 3, "o", 1080, "bottom-left")[1]
    assert "(W-w)/2:(H-h)/2" in logo_overlay_filters("v", 3, "o", 1080, "center")[1]


def test_resolve_file(tmp_path):
    f = tmp_path / "logo.png"
    f.write_bytes(b"x")
    assert resolve_file("logo.png", tmp_path) == f.resolve()
    assert resolve_file("nahi.png", tmp_path) is None
    assert resolve_file(None) is None
