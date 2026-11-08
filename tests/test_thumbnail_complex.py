from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.services import thumbnail
from app.services.thumbnail import ThumbnailError, make_thumbnail
from app.services.thumbnail_ass import build_thumbnail_ass, pick_font_size, render_complex_thumbnail

HINDI = "\u0928\u092e\u0938\u094d\u0924\u0947 \u0926\u094b\u0938\u094d\u0924\u094b\u0902"


def make_frame(tmp_path):
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (1280, 720), (10, 20, 30)).save(frame)
    return frame


def make_fonts(tmp_path):
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "x.ttf").write_bytes(b"x")
    return fonts


class FakeRunner:
    def __init__(self, sizes=None, code=0):
        self.calls = []
        self.sizes = sizes or {}
        self.code = code

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.code == 0:
            quality = args[args.index("-q:v") + 1]
            Path(args[-1]).write_bytes(b"x" * self.sizes.get(quality, 1000))
        return SimpleNamespace(returncode=self.code, stderr="boom")


def test_build_thumbnail_ass_has_font_text_and_centering():
    ass = build_thumbnail_ass(HINDI, "Noto Sans Devanagari")
    assert "Noto Sans Devanagari" in ass
    assert HINDI in ass
    assert "{\\an5}" in ass
    assert "PlayResX: 1080" in ass


def test_pick_font_size_shrinks_for_longer_text():
    assert pick_font_size("a" * 5) > pick_font_size("a" * 30) > pick_font_size("a" * 80)


def test_render_complex_thumbnail_runs_ffmpeg_with_ass_filter(tmp_path):
    runner = FakeRunner()
    out = render_complex_thumbnail(make_frame(tmp_path), HINDI, tmp_path / "thumb.jpg", make_fonts(tmp_path),
                                   runner=runner)
    args, kwargs = runner.calls[0]
    vf = args[args.index("-vf") + 1]
    assert "ass=thumb.ass:fontsdir=fonts" in vf
    assert "scale=1080:1920" in vf
    assert Path(kwargs["cwd"]).name == "thumb_ass"
    assert out.exists()
    assert HINDI in (out.parent / "thumb_ass" / "thumb.ass").read_text(encoding="utf-8")


def test_render_retries_with_lower_quality_when_file_is_too_big(tmp_path):
    runner = FakeRunner(sizes={"3": 3_000_000})
    out = render_complex_thumbnail(make_frame(tmp_path), HINDI, tmp_path / "thumb.jpg", make_fonts(tmp_path),
                                   runner=runner)
    assert len(runner.calls) == 2
    assert out.stat().st_size <= 2_000_000


def test_render_failure_raises(tmp_path):
    with pytest.raises(ThumbnailError):
        render_complex_thumbnail(make_frame(tmp_path), HINDI, tmp_path / "thumb.jpg", make_fonts(tmp_path),
                                 runner=FakeRunner(code=1))


def test_make_thumbnail_sends_hindi_text_to_libass(monkeypatch, tmp_path):
    record = {}

    def fake_render(frame, text, out, fonts_dir, size=(1080, 1920)):
        record.update(text=text, fonts_dir=fonts_dir)
        return Path(out)

    monkeypatch.setattr(thumbnail, "render_complex_thumbnail", fake_render)
    make_thumbnail(make_frame(tmp_path), HINDI, tmp_path / "t.jpg", font_path=tmp_path / "fonts" / "arialbd.ttf")
    assert record["text"] == HINDI
    assert Path(record["fonts_dir"]) == tmp_path / "fonts"


def test_latin_text_does_not_use_libass(monkeypatch, tmp_path):
    def boom(*args, **kwargs):
        raise AssertionError("libass nahi chalna chahiye")

    monkeypatch.setattr(thumbnail, "render_complex_thumbnail", boom)
    out = make_thumbnail(make_frame(tmp_path), "Black holes", tmp_path / "t.jpg")
    assert Image.open(out).size == (1080, 1920)
