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
    assert "ADD COLUMN format VARCHAR" in sql
    assert "ADD COLUMN thumbnail_url VARCHAR" in sql
    assert "ADD COLUMN in_collection BOOLEAN DEFAULT false NOT NULL" in sql
    assert "ADD COLUMN collection_added_at TIMESTAMP WITH TIME ZONE" in sql
    assert "ADD COLUMN collection_removed_at TIMESTAMP WITH TIME ZONE" in sql
    assert "ADD COLUMN last_discogs_sync_at TIMESTAMP WITH TIME ZONE" in sql
    assert "ADD COLUMN discogs_instance_id BIGINT" in sql
    assert "CREATE INDEX idx_releases_in_collection" in sql
    assert "CREATE INDEX idx_releases_collection_added_at" in sql
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
    assert "CREATE TABLE collection_sync_jobs" in sql
    assert "CREATE INDEX idx_collection_sync_jobs_status" in sql
    assert "CREATE INDEX idx_collection_sync_jobs_status_updated_at" in sql
    assert "CREATE TABLE collection_settings" in sql
    assert "source_of_truth VARCHAR(20) DEFAULT 'APP' NOT NULL" in sql
    assert "ck_collection_settings_source_of_truth" in sql
    assert "CREATE TABLE provider_integrations" in sql
    assert "access_token_ciphertext TEXT" in sql
    assert "external_user_id VARCHAR(255)" in sql
    assert "external_username VARCHAR(255)" in sql
    assert "CREATE INDEX idx_provider_integrations_provider_user_id" in sql
    assert "CREATE TABLE user_accounts" in sql
    assert "uq_user_accounts_normalized_email" in sql
    assert "CREATE TABLE auth_sessions" in sql
    assert "uq_auth_sessions_refresh_token_hash" in sql
    assert "CREATE INDEX idx_auth_sessions_user_id" in sql
    assert "CREATE TABLE consumed_refresh_tokens" in sql
    assert "uq_consumed_refresh_tokens_hash" in sql
    assert "CREATE INDEX idx_consumed_refresh_tokens_refresh_token_hash" in sql
    assert "CREATE TABLE email_verification_codes" in sql
    assert "CREATE INDEX idx_email_verification_codes_code_hash" in sql
    assert "ADD COLUMN failed_attempt_count INTEGER DEFAULT '0' NOT NULL" in sql
    assert "ADD COLUMN failed_attempt_limited_until TIMESTAMP WITH TIME ZONE" in sql
    assert "CREATE TABLE password_reset_codes" in sql
    assert "CREATE INDEX idx_password_reset_codes_code_hash" in sql
    assert "CREATE TABLE user_entitlements" in sql
    assert "CREATE TABLE usage_events" in sql
    assert "CREATE INDEX idx_usage_events_capability" in sql
    assert "CREATE INDEX idx_usage_events_user_capability_time" in sql
    assert "CREATE TABLE account_deletion_audits" in sql
    assert "CREATE INDEX idx_account_deletion_audits_deleted_at" in sql
    assert "CREATE TABLE auth_audit_events" in sql
    assert "CREATE INDEX idx_auth_audit_events_user_time" in sql
    assert "CREATE INDEX idx_auth_audit_events_event_type_time" in sql
    assert "ALTER TABLE session_moods ADD COLUMN user_id VARCHAR(36)" in sql
    assert "uq_session_moods_user_name" in sql
    assert "CREATE INDEX idx_session_moods_user_custom" in sql
