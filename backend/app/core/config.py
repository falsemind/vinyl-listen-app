from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    database_url: str

    database_echo: bool = False

    discogs_token: str | None = None

    api_rate_limit_per_minute: int = 60

    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
