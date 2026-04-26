from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

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

    log_level: str = "INFO"


settings = Settings()
