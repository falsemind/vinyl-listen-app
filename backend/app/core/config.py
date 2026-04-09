from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    database_url: str = "postgresql://postgres:postgres@localhost:5432/vinyl"

    discogs_token: str | None = None

    api_rate_limit_per_minute: int = 60

    database_echo: bool = False

    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
