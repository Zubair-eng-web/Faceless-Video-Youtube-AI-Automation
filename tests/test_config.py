from app.core.config import Settings


def make(tmp_path, **kwargs):
    return Settings(
        _env_file=None,
        output_dir=tmp_path / "output",
        cache_dir=tmp_path / "cache",
        music_dir=tmp_path / "music",
        fonts_dir=tmp_path / "fonts",
        db_path=tmp_path / "data" / "app.db",
        **kwargs,
    )


def test_video_format_is_vertical(tmp_path):
    s = make(tmp_path)
    assert (s.video_width, s.video_height) == (1080, 1920)
    assert s.video_height > s.video_width


def test_default_model(tmp_path):
    assert make(tmp_path).gemini_model == "gemini-3.1-flash-lite"


def test_ensure_dirs_creates_folders(tmp_path):
    s = make(tmp_path)
    s.ensure_dirs()
    for folder in (s.output_dir, s.cache_dir, s.music_dir, s.fonts_dir, s.db_path.parent):
        assert folder.is_dir()


def test_missing_keys_detects_empty_and_placeholder(tmp_path):
    s = make(tmp_path, gemini_api_key="", pixabay_api_key="your_pixabay_key_here")
    assert s.missing_keys() == ["GEMINI_API_KEY", "PIXABAY_API_KEY"]


def test_missing_keys_empty_when_keys_set(tmp_path):
    s = make(tmp_path, gemini_api_key="abc123456", pixabay_api_key="xyz123456")
    assert s.missing_keys() == []
