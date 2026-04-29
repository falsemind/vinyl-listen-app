from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"))

    database_url: str

    database_echo: bool = False

    discogs_token: str | None = None
    discogs_base_url: str
    discogs_user_agent: str = "vinyl-listen-app/0.1.0"
    discogs_request_timeout_seconds: float = 10.0
    discogs_cache_ttl_seconds: int = 86400

    api_rate_limit_per_minute: int = 60

    identify_easyocr_enabled: bool = False
    identify_easyocr_gpu: bool = False
    identify_easyocr_min_confidence: float = 0.35
    identify_easyocr_max_image_dimension: int = 800
    identify_geometry_preprocess_enabled: bool = False
    identify_geometry_preprocess_max_variants: int = 5
    identify_debug_preprocess_images_enabled: bool = False
    identify_debug_preprocess_images_dir: str = "identify_ocr_images"

    log_level: str = "INFO"


settings = Settings()
