from pathlib import Path

from alembic.config import Config

from alembic import command


def test_alembic_upgrade_sql_contains_documented_constraints_and_indexes(monkeypatch, capsys) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    alembic_ini_path = backend_root / "alembic.ini"

    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/testdb")

    config = Config(str(alembic_ini_path))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", "postgresql://test:test@localhost/testdb")

    command.upgrade(config, "head", sql=True)

    sql = capsys.readouterr().out

    assert "uq_releases_discogs_release_id" in sql
    assert "UNIQUE (discogs_release_id)" in sql
    assert "UNIQUE (name)" in sql
    assert "fk_sessions_release_id_releases" in sql
    assert "REFERENCES releases (id)" in sql
    assert "CREATE INDEX idx_releases_artist" in sql
    assert "CREATE INDEX idx_releases_title" in sql
    assert "CREATE INDEX idx_releases_genres" in sql
    assert "CREATE INDEX idx_releases_styles" in sql
    assert "CREATE INDEX idx_sessions_release_id" in sql
    assert "CREATE INDEX idx_sessions_played_at" in sql
    assert "CREATE INDEX idx_discogs_release_cache_last_accessed_at" in sql
    assert "CREATE TABLE identify_jobs" in sql
    assert "CREATE INDEX idx_identify_jobs_status" in sql
    assert "ALTER TABLE identify_jobs ADD COLUMN client_key" in sql
    assert "CREATE INDEX idx_identify_jobs_client_key_status" in sql
    assert "CREATE INDEX idx_identify_jobs_expires_at" in sql
    assert "CREATE TABLE ai_chat_sessions" in sql
    assert "CREATE TABLE ai_chat_messages" in sql
    assert "fk_ai_chat_messages_conversation_id_ai_chat_sessions" in sql
    assert "CREATE INDEX idx_ai_chat_messages_conversation_created" in sql
    assert "CREATE TABLE spotify_listening_import_batches" in sql
    assert "CREATE TABLE spotify_listening_events" in sql
    assert "uq_spotify_listening_events_event_key" in sql
    assert "fk_spotify_events_import_batch_id_spotify_import_batches" in sql
    assert "CREATE INDEX idx_spotify_events_artist" in sql
    assert "CREATE INDEX idx_spotify_events_year_month_artist" in sql
    assert "CREATE TABLE spotify_artist_stats" in sql
    assert "CREATE TABLE spotify_album_stats" in sql
    assert "CREATE TABLE spotify_track_stats" in sql
    assert "CREATE TABLE spotify_hourly_stats" in sql
    assert "CREATE TABLE spotify_monthly_artist_stats" in sql
    assert "CREATE TABLE spotify_skip_stats" in sql
    assert "CREATE TABLE spotify_vinyl_artist_matches" in sql
    assert "CREATE TABLE spotify_vinyl_release_matches" in sql
    assert "fk_spotify_release_matches_release_id_releases" in sql
    assert "CREATE INDEX idx_spotify_vinyl_release_matches_artist" in sql
