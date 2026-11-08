"""Poore project ki settings: .env se parhi jati hain."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys
    gemini_api_key: str = ""
    pixabay_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"

    # AI provider aur limits (.env: AI_PROVIDER, GEMINI_MAX_ATTEMPTS, GEMINI_RETRY_DELAY, GEMINI_MIN_INTERVAL_SECONDS)
    # GEMINI_MIN_INTERVAL_SECONDS: do requests ke beech kam az kam itne second (free tier ke liye 4 rakhein, paid ke liye 0)
    ai_provider: str = "gemini"
    gemini_max_attempts: int = 4
    gemini_retry_delay: float = 5.0
    gemini_min_interval_seconds: float = 0.0

    # Folders
    output_dir: Path = BASE_DIR / "output"
    cache_dir: Path = BASE_DIR / "assets" / "cache"
    music_dir: Path = BASE_DIR / "assets" / "music"
    fonts_dir: Path = BASE_DIR / "assets" / "fonts"
    db_path: Path = BASE_DIR / "data" / "app.db"

    # Video format (vertical 9:16, Shorts)
    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30

    # Long-form video format (landscape 16:9)
    long_video_width: int = 1920
    long_video_height: int = 1080

    # Publishing (.env se badal sakte hain: AUTO_PUBLISH, DEFAULT_PRIVACY, DAILY_UPLOAD_LIMIT, PUBLISH_CHECK_MINUTES)
    auto_publish: bool = False
    default_privacy: str = "private"
    daily_upload_limit: int = 5
    publish_check_minutes: int = 5

    # Auto production (.env: AUTO_PRODUCE, PRODUCE_CHECK_MINUTES)
    auto_produce: bool = False
    produce_check_minutes: int = 10

    def ensure_dirs(self) -> None:
        for folder in (self.output_dir, self.cache_dir, self.music_dir, self.fonts_dir, self.db_path.parent):
            folder.mkdir(parents=True, exist_ok=True)

    def missing_keys(self) -> list[str]:
        """Jo keys khali ya placeholder hain unke naam."""
        missing = []
        for name, value in (("GEMINI_API_KEY", self.gemini_api_key), ("PIXABAY_API_KEY", self.pixabay_api_key)):
            if not value or value.startswith("your_"):
                missing.append(name)
        return missing


settings = Settings()


def _mask(value: str) -> str:
    return f"{value[:3]}...{value[-3:]} (len {len(value)})" if len(value) > 6 else "KHALI"


if __name__ == "__main__":
    settings.ensure_dirs()
    print("Base folder :", BASE_DIR)
    print("AI provider :", settings.ai_provider)
    print("Gemini model:", settings.gemini_model)
    print("Gemini key  :", _mask(settings.gemini_api_key))
    print("Pixabay key :", _mask(settings.pixabay_api_key))
    print("Gemini limit:", f"{settings.gemini_max_attempts} attempts, min gap {settings.gemini_min_interval_seconds}s")
    print("Shorts size :", f"{settings.video_width}x{settings.video_height} @ {settings.video_fps}fps")
    print("Long size   :", f"{settings.long_video_width}x{settings.long_video_height}")
    print("Missing keys:", settings.missing_keys() or "koi nahi")