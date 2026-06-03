"""Add Spotify listening import tables.

Revision ID: 4e2a1c9d8b70
Revises: c8f2d4a9b6e1
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e2a1c9d8b70"
down_revision: str | Sequence[str] | None = "c8f2d4a9b6e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "spotify_listening_import_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_paths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_spotify_import_batches_status", "spotify_listening_import_batches", ["status"])
    op.create_index("idx_spotify_import_batches_started_at", "spotify_listening_import_batches", ["started_at"])

    op.create_table(
        "spotify_listening_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("import_batch_id", sa.String(length=36), nullable=True),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("played_date", sa.Date(), nullable=False),
        sa.Column("played_hour", sa.Integer(), nullable=False),
        sa.Column("played_weekday", sa.Integer(), nullable=False),
        sa.Column("played_year_month", sa.String(length=7), nullable=False),
        sa.Column("ms_played", sa.BigInteger(), nullable=False),
        sa.Column("conn_country", sa.String(length=16), nullable=True),
        sa.Column("track_name", sa.String(length=512), nullable=False),
        sa.Column("artist_name", sa.String(length=512), nullable=False),
        sa.Column("album_name", sa.String(length=512), nullable=True),
        sa.Column("normalized_track_name", sa.String(length=512), nullable=False),
        sa.Column("normalized_artist_name", sa.String(length=512), nullable=False),
        sa.Column("normalized_album_name", sa.String(length=512), nullable=True),
        sa.Column("reason_start", sa.String(length=64), nullable=True),
        sa.Column("reason_end", sa.String(length=64), nullable=True),
        sa.Column("shuffle", sa.Boolean(), nullable=True),
        sa.Column("skipped", sa.Boolean(), nullable=True),
        sa.Column("offline", sa.Boolean(), nullable=True),
        sa.Column("offline_timestamp", sa.String(length=64), nullable=True),
        sa.Column("is_meaningful_listen", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["spotify_listening_import_batches.id"],
            name="fk_spotify_events_import_batch_id_spotify_import_batches",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_spotify_listening_events_event_key"),
    )
    op.create_index("idx_spotify_events_played_at", "spotify_listening_events", ["played_at"])
    op.create_index("idx_spotify_events_played_date", "spotify_listening_events", ["played_date"])
    op.create_index("idx_spotify_events_artist", "spotify_listening_events", ["normalized_artist_name"])
    op.create_index("idx_spotify_events_album", "spotify_listening_events", ["normalized_album_name"])
    op.create_index("idx_spotify_events_track", "spotify_listening_events", ["normalized_track_name"])
    op.create_index(
        "idx_spotify_events_year_month_artist",
        "spotify_listening_events",
        ["played_year_month", "normalized_artist_name"],
    )
    op.create_index("idx_spotify_events_meaningful", "spotify_listening_events", ["is_meaningful_listen"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_spotify_events_meaningful", table_name="spotify_listening_events")
    op.drop_index("idx_spotify_events_year_month_artist", table_name="spotify_listening_events")
    op.drop_index("idx_spotify_events_track", table_name="spotify_listening_events")
    op.drop_index("idx_spotify_events_album", table_name="spotify_listening_events")
    op.drop_index("idx_spotify_events_artist", table_name="spotify_listening_events")
    op.drop_index("idx_spotify_events_played_date", table_name="spotify_listening_events")
    op.drop_index("idx_spotify_events_played_at", table_name="spotify_listening_events")
    op.drop_table("spotify_listening_events")
    op.drop_index("idx_spotify_import_batches_started_at", table_name="spotify_listening_import_batches")
    op.drop_index("idx_spotify_import_batches_status", table_name="spotify_listening_import_batches")
    op.drop_table("spotify_listening_import_batches")
