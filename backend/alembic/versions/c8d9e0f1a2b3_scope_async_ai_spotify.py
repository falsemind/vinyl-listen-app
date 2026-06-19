"""scope async jobs ai chat and spotify data

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-06-18 00:00:00.000000

"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_OWNER_EMAIL_ENV = "VINYL_LEGACY_OWNER_EMAIL"
USER_SCOPED_TABLES = (
    "identify_jobs",
    "ai_chat_sessions",
    "spotify_listening_import_batches",
    "spotify_listening_events",
    "spotify_artist_stats",
    "spotify_album_stats",
    "spotify_track_stats",
    "spotify_hourly_stats",
    "spotify_monthly_artist_stats",
    "spotify_skip_stats",
    "spotify_vinyl_artist_matches",
    "spotify_vinyl_release_matches",
)


def upgrade() -> None:
    """Upgrade schema."""
    _add_owner_columns()

    legacy_owner_id = None
    if not context.is_offline_mode():
        bind = op.get_bind()
        legacy_owner_id = _resolve_legacy_owner_id(bind)
        if legacy_owner_id is not None:
            _backfill_legacy_owner(bind, legacy_owner_id=legacy_owner_id)

    _backfill_public_ai_conversation_ids()
    _backfill_spotify_scoped_keys()
    _replace_constraints()
    _require_owner_columns()
    _create_owner_indexes()


def downgrade() -> None:
    """Downgrade schema."""
    _drop_owner_indexes()
    _drop_new_constraints()

    op.create_unique_constraint(
        "uq_spotify_listening_events_event_key",
        "spotify_listening_events",
        ["event_key"],
    )
    op.create_unique_constraint(
        "uq_spotify_album_stats_artist_album",
        "spotify_album_stats",
        ["normalized_artist_name", "normalized_album_name"],
    )
    op.create_unique_constraint(
        "uq_spotify_track_stats_artist_album_track",
        "spotify_track_stats",
        ["normalized_artist_name", "normalized_album_name", "normalized_track_name"],
    )
    op.create_unique_constraint(
        "uq_spotify_monthly_artist_stats",
        "spotify_monthly_artist_stats",
        ["played_year_month", "normalized_artist_name"],
    )
    op.create_unique_constraint(
        "uq_spotify_release_match",
        "spotify_vinyl_release_matches",
        ["release_id", "normalized_artist_name", "normalized_album_name"],
    )

    op.drop_constraint("spotify_artist_stats_pkey", "spotify_artist_stats", type_="primary")
    op.create_primary_key("spotify_artist_stats_pkey", "spotify_artist_stats", ["normalized_artist_name"])
    op.drop_constraint("spotify_hourly_stats_pkey", "spotify_hourly_stats", type_="primary")
    op.create_primary_key("spotify_hourly_stats_pkey", "spotify_hourly_stats", ["played_hour"])
    op.drop_constraint("spotify_vinyl_artist_matches_pkey", "spotify_vinyl_artist_matches", type_="primary")
    op.create_primary_key(
        "spotify_vinyl_artist_matches_pkey",
        "spotify_vinyl_artist_matches",
        ["normalized_artist_name"],
    )

    for table_name in reversed(USER_SCOPED_TABLES):
        op.drop_constraint(f"fk_{table_name}_user_id_user_accounts", table_name, type_="foreignkey")
        op.drop_column(table_name, "user_id")

    op.drop_column("ai_chat_sessions", "public_conversation_id")
    op.drop_column("spotify_artist_stats", "stat_key")
    op.drop_column("spotify_hourly_stats", "stat_key")
    op.drop_column("spotify_vinyl_artist_matches", "match_key")


def _add_owner_columns() -> None:
    for table_name in USER_SCOPED_TABLES:
        op.add_column(table_name, sa.Column("user_id", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            f"fk_{table_name}_user_id_user_accounts",
            table_name,
            "user_accounts",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.add_column("ai_chat_sessions", sa.Column("public_conversation_id", sa.String(length=36), nullable=True))
    op.add_column("spotify_artist_stats", sa.Column("stat_key", sa.String(length=64), nullable=True))
    op.add_column("spotify_hourly_stats", sa.Column("stat_key", sa.String(length=64), nullable=True))
    op.add_column("spotify_vinyl_artist_matches", sa.Column("match_key", sa.String(length=64), nullable=True))


def _backfill_public_ai_conversation_ids() -> None:
    op.execute("UPDATE ai_chat_sessions SET public_conversation_id = id WHERE public_conversation_id IS NULL")


def _backfill_spotify_scoped_keys() -> None:
    op.execute("""
        UPDATE spotify_artist_stats
        SET stat_key = md5(user_id || ':' || normalized_artist_name)
        WHERE stat_key IS NULL
        """)
    op.execute("""
        UPDATE spotify_hourly_stats
        SET stat_key = md5(user_id || ':' || played_hour::text)
        WHERE stat_key IS NULL
        """)
    op.execute("""
        UPDATE spotify_vinyl_artist_matches
        SET match_key = md5(user_id || ':' || normalized_artist_name)
        WHERE match_key IS NULL
        """)


def _replace_constraints() -> None:
    op.drop_constraint("uq_spotify_listening_events_event_key", "spotify_listening_events", type_="unique")
    op.drop_constraint("uq_spotify_album_stats_artist_album", "spotify_album_stats", type_="unique")
    op.drop_constraint("uq_spotify_track_stats_artist_album_track", "spotify_track_stats", type_="unique")
    op.drop_constraint("uq_spotify_monthly_artist_stats", "spotify_monthly_artist_stats", type_="unique")
    op.drop_constraint("uq_spotify_release_match", "spotify_vinyl_release_matches", type_="unique")

    op.drop_constraint("spotify_artist_stats_pkey", "spotify_artist_stats", type_="primary")
    op.create_primary_key("spotify_artist_stats_pkey", "spotify_artist_stats", ["stat_key"])
    op.drop_constraint("spotify_hourly_stats_pkey", "spotify_hourly_stats", type_="primary")
    op.create_primary_key("spotify_hourly_stats_pkey", "spotify_hourly_stats", ["stat_key"])
    op.drop_constraint("spotify_vinyl_artist_matches_pkey", "spotify_vinyl_artist_matches", type_="primary")
    op.create_primary_key("spotify_vinyl_artist_matches_pkey", "spotify_vinyl_artist_matches", ["match_key"])

    op.create_unique_constraint(
        "uq_ai_chat_sessions_user_public_id",
        "ai_chat_sessions",
        ["user_id", "public_conversation_id"],
    )
    op.create_unique_constraint(
        "uq_spotify_listening_events_user_event_key",
        "spotify_listening_events",
        ["user_id", "event_key"],
    )
    op.create_unique_constraint(
        "uq_spotify_artist_stats_user_artist",
        "spotify_artist_stats",
        ["user_id", "normalized_artist_name"],
    )
    op.create_unique_constraint(
        "uq_spotify_album_stats_user_artist_album",
        "spotify_album_stats",
        ["user_id", "normalized_artist_name", "normalized_album_name"],
    )
    op.create_unique_constraint(
        "uq_spotify_track_stats_user_artist_album_track",
        "spotify_track_stats",
        ["user_id", "normalized_artist_name", "normalized_album_name", "normalized_track_name"],
    )
    op.create_unique_constraint(
        "uq_spotify_hourly_stats_user_hour",
        "spotify_hourly_stats",
        ["user_id", "played_hour"],
    )
    op.create_unique_constraint(
        "uq_spotify_monthly_artist_stats_user_month_artist",
        "spotify_monthly_artist_stats",
        ["user_id", "played_year_month", "normalized_artist_name"],
    )
    op.create_unique_constraint(
        "uq_spotify_vinyl_artist_matches_user_artist",
        "spotify_vinyl_artist_matches",
        ["user_id", "normalized_artist_name"],
    )
    op.create_unique_constraint(
        "uq_spotify_release_match_user_release_artist_album",
        "spotify_vinyl_release_matches",
        ["user_id", "release_id", "normalized_artist_name", "normalized_album_name"],
    )


def _require_owner_columns() -> None:
    op.alter_column("ai_chat_sessions", "public_conversation_id", existing_type=sa.String(length=36), nullable=False)
    op.alter_column("spotify_artist_stats", "stat_key", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("spotify_hourly_stats", "stat_key", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("spotify_vinyl_artist_matches", "match_key", existing_type=sa.String(length=64), nullable=False)

    for table_name in USER_SCOPED_TABLES:
        op.alter_column(table_name, "user_id", existing_type=sa.String(length=36), nullable=False)


def _create_owner_indexes() -> None:
    op.create_index("idx_identify_jobs_user_status", "identify_jobs", ["user_id", "status"])
    op.create_index("idx_identify_jobs_user_client_status", "identify_jobs", ["user_id", "client_key", "status"])
    op.create_index("idx_ai_chat_sessions_user_updated_at", "ai_chat_sessions", ["user_id", "updated_at"])
    op.create_index(
        "idx_spotify_import_batches_user_status",
        "spotify_listening_import_batches",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_spotify_import_batches_user_started_at",
        "spotify_listening_import_batches",
        ["user_id", "started_at"],
    )
    op.create_index("idx_spotify_events_user_played_at", "spotify_listening_events", ["user_id", "played_at"])
    op.create_index("idx_spotify_events_user_artist", "spotify_listening_events", ["user_id", "normalized_artist_name"])
    op.create_index(
        "idx_spotify_events_user_year_month_artist",
        "spotify_listening_events",
        ["user_id", "played_year_month", "normalized_artist_name"],
    )
    op.create_index("idx_spotify_artist_stats_user_total_ms", "spotify_artist_stats", ["user_id", "total_ms_played"])
    op.create_index("idx_spotify_album_stats_user_artist", "spotify_album_stats", ["user_id", "normalized_artist_name"])
    op.create_index("idx_spotify_album_stats_user_total_ms", "spotify_album_stats", ["user_id", "total_ms_played"])
    op.create_index("idx_spotify_track_stats_user_artist", "spotify_track_stats", ["user_id", "normalized_artist_name"])
    op.create_index("idx_spotify_track_stats_user_total_ms", "spotify_track_stats", ["user_id", "total_ms_played"])
    op.create_index(
        "idx_spotify_monthly_artist_stats_user_artist",
        "spotify_monthly_artist_stats",
        ["user_id", "normalized_artist_name"],
    )
    op.create_index(
        "idx_spotify_monthly_artist_stats_user_month",
        "spotify_monthly_artist_stats",
        ["user_id", "played_year_month"],
    )
    op.create_index(
        "idx_spotify_vinyl_artist_matches_user_confidence",
        "spotify_vinyl_artist_matches",
        ["user_id", "confidence_score"],
    )
    op.create_index(
        "idx_spotify_vinyl_release_matches_user_artist",
        "spotify_vinyl_release_matches",
        ["user_id", "normalized_artist_name"],
    )
    op.create_index(
        "idx_spotify_vinyl_release_matches_user_confidence",
        "spotify_vinyl_release_matches",
        ["user_id", "confidence_score"],
    )


def _drop_owner_indexes() -> None:
    index_specs = (
        ("idx_spotify_vinyl_release_matches_user_confidence", "spotify_vinyl_release_matches"),
        ("idx_spotify_vinyl_release_matches_user_artist", "spotify_vinyl_release_matches"),
        ("idx_spotify_vinyl_artist_matches_user_confidence", "spotify_vinyl_artist_matches"),
        ("idx_spotify_monthly_artist_stats_user_month", "spotify_monthly_artist_stats"),
        ("idx_spotify_monthly_artist_stats_user_artist", "spotify_monthly_artist_stats"),
        ("idx_spotify_track_stats_user_total_ms", "spotify_track_stats"),
        ("idx_spotify_track_stats_user_artist", "spotify_track_stats"),
        ("idx_spotify_album_stats_user_total_ms", "spotify_album_stats"),
        ("idx_spotify_album_stats_user_artist", "spotify_album_stats"),
        ("idx_spotify_artist_stats_user_total_ms", "spotify_artist_stats"),
        ("idx_spotify_events_user_year_month_artist", "spotify_listening_events"),
        ("idx_spotify_events_user_artist", "spotify_listening_events"),
        ("idx_spotify_events_user_played_at", "spotify_listening_events"),
        ("idx_spotify_import_batches_user_started_at", "spotify_listening_import_batches"),
        ("idx_spotify_import_batches_user_status", "spotify_listening_import_batches"),
        ("idx_ai_chat_sessions_user_updated_at", "ai_chat_sessions"),
        ("idx_identify_jobs_user_client_status", "identify_jobs"),
        ("idx_identify_jobs_user_status", "identify_jobs"),
    )
    for index_name, table_name in index_specs:
        op.drop_index(index_name, table_name=table_name)


def _drop_new_constraints() -> None:
    for constraint_name, table_name in (
        ("uq_spotify_release_match_user_release_artist_album", "spotify_vinyl_release_matches"),
        ("uq_spotify_vinyl_artist_matches_user_artist", "spotify_vinyl_artist_matches"),
        ("uq_spotify_monthly_artist_stats_user_month_artist", "spotify_monthly_artist_stats"),
        ("uq_spotify_hourly_stats_user_hour", "spotify_hourly_stats"),
        ("uq_spotify_track_stats_user_artist_album_track", "spotify_track_stats"),
        ("uq_spotify_album_stats_user_artist_album", "spotify_album_stats"),
        ("uq_spotify_artist_stats_user_artist", "spotify_artist_stats"),
        ("uq_spotify_listening_events_user_event_key", "spotify_listening_events"),
        ("uq_ai_chat_sessions_user_public_id", "ai_chat_sessions"),
    ):
        op.drop_constraint(constraint_name, table_name, type_="unique")


def _resolve_legacy_owner_id(bind: Connection) -> str | None:
    if not _has_legacy_user_scoped_rows(bind):
        return None

    owner_email = os.getenv(LEGACY_OWNER_EMAIL_ENV)
    if owner_email:
        row = bind.execute(
            sa.text("""
                SELECT id
                FROM user_accounts
                WHERE lower(email) = lower(:email)
                  AND is_active = TRUE
                  AND deleted_at IS NULL
                """),
            {"email": owner_email},
        ).one_or_none()
        if row is None:
            raise RuntimeError(f"{LEGACY_OWNER_EMAIL_ENV} does not match an active account.")
        return str(row[0])

    owner_ids = [str(row[0]) for row in bind.execute(sa.text("""
                SELECT id
                FROM user_accounts
                WHERE is_active = TRUE
                  AND deleted_at IS NULL
                ORDER BY created_at ASC, id ASC
                LIMIT 2
                """))]
    if len(owner_ids) == 1:
        return owner_ids[0]
    if not owner_ids:
        raise RuntimeError(
            "Legacy async/AI/Spotify data exists but no active account is available. "
            "Create/register the owner account before upgrading, or reset local data."
        )
    raise RuntimeError(
        "Legacy async/AI/Spotify data exists but multiple active accounts are available. "
        f"Set {LEGACY_OWNER_EMAIL_ENV} to the intended owner email before upgrading."
    )


def _has_legacy_user_scoped_rows(bind: Connection) -> bool:
    checks = " OR ".join(
        f"EXISTS (SELECT 1 FROM {table_name} WHERE user_id IS NULL)" for table_name in USER_SCOPED_TABLES
    )
    return bool(bind.execute(sa.text(f"SELECT {checks}")).scalar())


def _backfill_legacy_owner(bind: Connection, *, legacy_owner_id: str) -> None:
    for table_name in USER_SCOPED_TABLES:
        bind.execute(
            sa.text(f"UPDATE {table_name} SET user_id = :legacy_owner_id WHERE user_id IS NULL"),
            {"legacy_owner_id": legacy_owner_id},
        )
