from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"), extra="ignore")

    database_profile: Literal["dev", "collection"] = "dev"
    database_url: str | None = None
    database_dev_url: str = "postgresql://vinyl:vinyl@localhost:5432/vinyl_dev"
    database_collection_url: str = "postgresql://vinyl:vinyl@localhost:5432/vinyl_collection"

    database_echo: bool = False
    max_page_limit: int = Field(default=250, ge=1)

    discogs_token_encryption_key: str | None = None
    discogs_base_url: str
    discogs_user_agent: str = "vinyl-listen-app/0.1.0"
    discogs_request_timeout_seconds: float = 10.0
    discogs_cache_ttl_seconds: int = 86400

    api_rate_limit_per_minute: int = 60
    inbound_rate_limit_enabled: bool = True
    inbound_rate_limit_backend: Literal["memory", "redis"] = "redis"
    inbound_default_rate_limit_per_minute: int = 300
    inbound_identify_rate_limit_per_minute: int = 30
    inbound_rate_limit_window_seconds: float = 60.0
    inbound_rate_limit_trust_proxy_headers: bool = False
    inbound_rate_limit_redis_url: str | None = None
    inbound_rate_limit_redis_key_prefix: str = "vinyl-listen-app:rate-limit"
    inbound_rate_limit_redis_fail_open: bool = True
    inbound_rate_limit_redis_timeout_seconds: float = 0.25

    auth_access_token_secret: str | None = None
    auth_access_token_lifetime_seconds: int = 900
    auth_refresh_token_lifetime_days: int = 30
    auth_inactivity_reauth_days: int = 7
    auth_password_argon2_time_cost: int = 3
    auth_password_argon2_memory_cost: int = 65536
    auth_password_argon2_parallelism: int = 4
    auth_password_argon2_hash_len: int = 32
    auth_password_argon2_salt_len: int = 16
    auth_code_hash_secret: str | None = None
    auth_email_code_length: int = 6
    auth_email_verification_code_ttl_minutes: int = 15
    auth_password_reset_code_ttl_minutes: int = 15
    auth_email_resend_cooldown_seconds: int = 60
    auth_code_failed_attempt_limit: int = Field(default=5, ge=1)
    auth_code_failed_attempt_lock_seconds: int = Field(default=300, ge=1)
    auth_email_delivery_backend: Literal["local", "mailgun"] = "local"
    auth_local_email_outbox_path: str = "auth-local-email-outbox.jsonl"
    auth_email_from_address: str = "noreply@vinyl-listen.local"
    mailgun_api_base_url: str = "https://api.mailgun.net"
    mailgun_api_key: str | None = None
    mailgun_domain: str | None = None

    entitlement_ocr_identify_free_limit: int = Field(default=25, ge=0)
    entitlement_ocr_identify_trial_limit: int = Field(default=100, ge=0)
    entitlement_ocr_identify_window_days: int = Field(default=30, ge=1)

    ai_chat_enabled: bool = False
    ai_chat_base_url: str | None = None
    ai_chat_endpoint_path: str = "/api/v1/chat"
    ai_chat_model: str | None = None
    ai_chat_api_key: str | None = None
    ai_chat_timeout_seconds: float = 60.0
    ai_chat_temperature: float = 0.2
    spotify_import_dir: str = "spotify_import"

    identify_ocr_backend: Literal["auto", "mlx_vlm", "paddleocr_vl", "tesseract"] = "auto"
    identify_max_concurrent_jobs: int = 1
    identify_max_active_jobs_per_client: int = 1
    identify_max_active_jobs_global: int = 0
    identify_stale_active_job_timeout_seconds: int = 900
    identify_capacity_retry_after_seconds: int = 5
    identify_ocr_tesseract_fallback_enabled: bool = True
    identify_mlx_vlm_service_url: str | None = None
    identify_mlx_vlm_endpoint_path: str = "/v1/chat/completions"
    identify_mlx_vlm_model_name: str = "PaddlePaddle/PaddleOCR-VL-1.5"
    identify_mlx_vlm_api_key: str | None = None
    identify_mlx_vlm_timeout_seconds: float = 30.0
    identify_mlx_vlm_max_image_dimension: int = 2048
    identify_mlx_vlm_max_tokens: int = 768
    identify_mlx_vlm_variant_names: str = "normalized,label_catalog_band,label_bottom_band,grayscale,sharpened"
    identify_mlx_vlm_max_variants: int = 3
    identify_mlx_vlm_prompt: str = (
        "Read only visible text from this vinyl record label image. Return compact JSON only. "
        "Use keys visible_lines, fields, catalog_numbers, and best_discogs_queries. "
        "visible_lines must contain exact visible OCR lines. fields may contain artist, title, label, barcode, and "
        "year only when visible. catalog_numbers must include visible catalog numbers such as DAT 095 or "
        "SCI LIMITED 012. best_discogs_queries should contain 1-3 concise Discogs search queries combining the "
        "strongest visible artist/title/catalog/label/track-title evidence. Do not use credit, copyright, mastering, "
        "manufacturing, or production text in fields or best_discogs_queries, but keep those lines in visible_lines "
        "when readable. Use null or [] for unknown values. Do not infer, guess, or add database metadata."
    )
    identify_paddleocr_device: str = "cpu"
    identify_paddleocr_vl_rec_backend: str | None = "mlx-vlm-server"
    identify_paddleocr_vl_rec_server_url: str | None = None
    identify_paddleocr_vl_rec_api_model_name: str = "PaddlePaddle/PaddleOCR-VL-1.5"
    identify_paddleocr_vl_rec_api_key: str | None = None
    identify_paddleocr_vl_rec_max_concurrency: int | None = None
    identify_paddleocr_timeout_seconds: float = 30.0
    identify_paddleocr_max_image_dimension: int = 1280
    identify_geometry_preprocess_enabled: bool = True
    identify_geometry_preprocess_max_variants: int = 5
    identify_debug_preprocess_images_enabled: bool = False
    identify_debug_preprocess_images_dir: str = "identify_ocr_images"

    log_level: str = "INFO"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url and self.database_url.strip():
            return self.database_url

        profile_urls = {
            "dev": self.database_dev_url,
            "collection": self.database_collection_url,
        }
        return profile_urls[self.database_profile]


settings = Settings()
