from app.core.config import Settings


def test_resolved_database_url_defaults_to_dev_profile() -> None:
    settings = Settings(_env_file=None, discogs_base_url="https://api.discogs.com")

    assert settings.database_profile == "dev"
    assert settings.resolved_database_url == "postgresql://vinyl:vinyl@localhost:5432/vinyl_dev"


def test_resolved_database_url_uses_collection_profile() -> None:
    settings = Settings(
        _env_file=None,
        database_profile="collection",
        discogs_base_url="https://api.discogs.com",
    )

    assert settings.resolved_database_url == "postgresql://vinyl:vinyl@localhost:5432/vinyl_collection"


def test_database_url_override_wins_over_profile() -> None:
    settings = Settings(
        _env_file=None,
        database_profile="collection",
        database_url="sqlite:///./test.db",
        discogs_base_url="https://api.discogs.com",
    )

    assert settings.resolved_database_url == "sqlite:///./test.db"


def test_discogs_collection_credentials_can_be_configured() -> None:
    settings = Settings(
        _env_file=None,
        discogs_base_url="https://api.discogs.com",
        discogs_username="username",
        discogs_token="token",
    )

    assert settings.discogs_username == "username"
    assert settings.discogs_token == "token"
