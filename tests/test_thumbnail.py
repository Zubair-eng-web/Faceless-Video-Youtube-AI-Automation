from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.services.thumbnail import ThumbnailError, extract_frame, fit_text, make_thumbnail, wrap_text


class FakeFont:
    def getlength(self, text):
        return len(text) * 10


def test_wrap_text_breaks_lines():
    assert wrap_text("aaa bbb ccc", FakeFont(), 70) == ["aaa bbb", "ccc"]


def test_wrap_text_keeps_long_single_word():
    assert wrap_text("abcdefghij", FakeFont(), 30) == ["abcdefghij"]


def test_fit_text_respects_max_lines():
    font, lines, size = fit_text("one two three four five six seven eight nine ten", None, 900, 700)
    assert len(lines) <= 4 or size == 56


def test_make_thumbnail_creates_vertical_jpeg(tmp_path):
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (1280, 720), (20, 60, 200)).save(frame)
    out = make_thumbnail(frame, "Black holes explained", tmp_path / "thumb.jpg")
    assert Image.open(out).size == (1080, 1920)
    assert out.stat().st_size <= 2_000_000


def test_make_thumbnail_rejects_empty_text(tmp_path):
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (100, 100)).save(frame)
    with pytest.raises(ThumbnailError):
        make_thumbnail(frame, "   ", tmp_path / "thumb.jpg")


def test_extract_frame_calls_ffmpeg(tmp_path):
    seen = {}

    def runner(args, **kwargs):
        seen["args"] = args
        Path(args[-1]).write_bytes(b"jpg")
        return SimpleNamespace(returncode=0, stderr="")

    out = extract_frame("seg.mp4", 1.0, tmp_path / "f.jpg", runner=runner)
    assert out.exists()
    assert "-ss" in seen["args"]
    assert "1.00" in seen["args"]


def test_extract_frame_raises_on_failure(tmp_path):
    def runner(args, **kwargs):
        return SimpleNamespace(returncode=1, stderr="boom")

    with pytest.raises(ThumbnailError):
        extract_frame("seg.mp4", 1.0, tmp_path / "f.jpg", runner=runner)
