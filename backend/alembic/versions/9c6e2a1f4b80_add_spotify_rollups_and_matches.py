"""Add Spotify rollup and collection match tables.

Revision ID: 9c6e2a1f4b80
Revises: 4e2a1c9d8b70
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c6e2a1f4b80"
down_revision: str | Sequence[str] | None = "4e2a1c9d8b70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "spotify_artist_stats",
        sa.Column("normalized_artist_name", sa.String(length=512), nullable=False),
        sa.Column("artist_name", sa.String(length=512), nullable=False),
        sa.Column("play_count", sa.Integer(), nullable=False),
        sa.Column("meaningful_play_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("total_ms_played", sa.BigInteger(), nullable=False),
        sa.Column("first_played_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_played_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("normalized_artist_name"),
    )
    op.create_index("idx_spotify_artist_stats_total_ms", "spotify_artist_stats", ["total_ms_played"])

    op.create_table(
        "spotify_album_stats",
        sa.Column("stat_key", sa.String(length=64), nullable=False),
        sa.Column("normalized_artist_name", sa.String(length=512), nullable=False),
        sa.Column("normalized_album_name", sa.String(length=512), nullable=False),
        sa.Column("artist_name", sa.String(length=512), nullable=False),
        sa.Column("album_name", sa.String(length=512), nullable=False),
        sa.Column("play_count", sa.Integer(), nullable=False),
        sa.Column("meaningful_play_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("total_ms_played", sa.BigInteger(), nullable=False),
        sa.Column("first_played_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_played_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("stat_key"),
        sa.UniqueConstraint(
            "normalized_artist_name",
            "normalized_album_name",
            name="uq_spotify_album_stats_artist_album",
        ),
    )
    op.create_index("idx_spotify_album_stats_artist", "spotify_album_stats", ["normalized_artist_name"])
    op.create_index("idx_spotify_album_stats_total_ms", "spotify_album_stats", ["total_ms_played"])

    op.create_table(
        "spotify_track_stats",
        sa.Column("stat_key", sa.String(length=64), nullable=False),
        sa.Column("normalized_artist_name", sa.String(length=512), nullable=False),
        sa.Column("normalized_album_name", sa.String(length=512), nullable=True),
        sa.Column("normalized_track_name", sa.String(length=512), nullable=False),
        sa.Column("artist_name", sa.String(length=512), nullable=False),
        sa.Column("album_name", sa.String(length=512), nullable=True),
        sa.Column("track_name", sa.String(length=512), nullable=False),
        sa.Column("play_count", sa.Integer(), nullable=False),
        sa.Column("meaningful_play_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("total_ms_played", sa.BigInteger(), nullable=False),
        sa.Column("first_played_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_played_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("stat_key"),
        sa.UniqueConstraint(
            "normalized_artist_name",
            "normalized_album_name",
            "normalized_track_name",
            name="uq_spotify_track_stats_artist_album_track",
        ),
    )
    op.create_index("idx_spotify_track_stats_artist", "spotify_track_stats", ["normalized_artist_name"])
    op.create_index("idx_spotify_track_stats_total_ms", "spotify_track_stats", ["total_ms_played"])

    op.create_table(
        "spotify_hourly_stats",
        sa.Column("played_hour", sa.Integer(), nullable=False),
        sa.Column("play_count", sa.Integer(), nullable=False),
        sa.Column("meaningful_play_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("total_ms_played", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("played_hour"),
    )

    op.create_table(
        "spotify_monthly_artist_stats",
        sa.Column("stat_key", sa.String(length=64), nullable=False),
        sa.Column("played_year_month", sa.String(length=7), nullable=False),
        sa.Column("normalized_artist_name", sa.String(length=512), nullable=False),
        sa.Column("artist_name", sa.String(length=512), nullable=False),
        sa.Column("play_count", sa.Integer(), nullable=False),
        sa.Column("meaningful_play_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("total_ms_played", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("stat_key"),
        sa.UniqueConstraint("played_year_month", "normalized_artist_name", name="uq_spotify_monthly_artist_stats"),
    )
    op.create_index(
        "idx_spotify_monthly_artist_stats_artist",
        "spotify_monthly_artist_stats",
        ["normalized_artist_name"],
    )
    op.create_index(
        "idx_spotify_monthly_artist_stats_month",
        "spotify_monthly_artist_stats",
        ["played_year_month"],
    )

    op.create_table(
        "spotify_skip_stats",
        sa.Column("stat_key", sa.String(length=64), nullable=False),
        sa.Column("skipped", sa.Boolean(), nullable=True),
        sa.Column("reason_end", sa.String(length=64), nullable=True),
        sa.Column("play_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("total_ms_played", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("stat_key"),
    )

    op.create_table(
        "spotify_vinyl_artist_matches",
        sa.Column("normalized_artist_name", sa.String(length=512), nullable=False),
        sa.Column("artist_name", sa.String(length=512), nullable=False),
        sa.Column("release_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("release_count", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("match_type", sa.String(length=40), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("normalized_artist_name"),
    )
    op.create_index(
        "idx_spotify_vinyl_artist_matches_confidence",
        "spotify_vinyl_artist_matches",
        ["confidence_score"],
    )

    op.create_table(
        "spotify_vinyl_release_matches",
        sa.Column("match_key", sa.String(length=64), nullable=False),
        sa.Column("release_id", sa.String(), nullable=False),
        sa.Column("normalized_artist_name", sa.String(length=512), nullable=False),
        sa.Column("normalized_album_name", sa.String(length=512), nullable=False),
        sa.Column("spotify_artist_name", sa.String(length=512), nullable=False),
        sa.Column("spotify_album_name", sa.String(length=512), nullable=False),
        sa.Column("release_artist", sa.String(length=512), nullable=False),
        sa.Column("release_title", sa.String(length=512), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("match_type", sa.String(length=40), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["releases.id"],
            name="fk_spotify_release_matches_release_id_releases",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("match_key"),
        sa.UniqueConstraint(
            "release_id",
            "normalized_artist_name",
            "normalized_album_name",
            name="uq_spotify_release_match",
        ),
    )
    op.create_index(
        "idx_spotify_vinyl_release_matches_artist",
        "spotify_vinyl_release_matches",
        ["normalized_artist_name"],
    )
    op.create_index(
        "idx_spotify_vinyl_release_matches_confidence",
        "spotify_vinyl_release_matches",
        ["confidence_score"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_spotify_vinyl_release_matches_confidence", table_name="spotify_vinyl_release_matches")
    op.drop_index("idx_spotify_vinyl_release_matches_artist", table_name="spotify_vinyl_release_matches")
    op.drop_table("spotify_vinyl_release_matches")
    op.drop_index("idx_spotify_vinyl_artist_matches_confidence", table_name="spotify_vinyl_artist_matches")
    op.drop_table("spotify_vinyl_artist_matches")
    op.drop_table("spotify_skip_stats")
    op.drop_index("idx_spotify_monthly_artist_stats_month", table_name="spotify_monthly_artist_stats")
    op.drop_index("idx_spotify_monthly_artist_stats_artist", table_name="spotify_monthly_artist_stats")
    op.drop_table("spotify_monthly_artist_stats")
    op.drop_table("spotify_hourly_stats")
    op.drop_index("idx_spotify_track_stats_total_ms", table_name="spotify_track_stats")
    op.drop_index("idx_spotify_track_stats_artist", table_name="spotify_track_stats")
    op.drop_table("spotify_track_stats")
    op.drop_index("idx_spotify_album_stats_total_ms", table_name="spotify_album_stats")
    op.drop_index("idx_spotify_album_stats_artist", table_name="spotify_album_stats")
    op.drop_table("spotify_album_stats")
    op.drop_index("idx_spotify_artist_stats_total_ms", table_name="spotify_artist_stats")
    op.drop_table("spotify_artist_stats")
