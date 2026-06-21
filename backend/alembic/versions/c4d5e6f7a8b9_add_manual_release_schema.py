"""add manual release schema

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-21 00:00:00.000000

Rollback note:
    The previous schema cannot represent app-owned manual releases because
    ``releases.discogs_release_id`` was required. Downgrading removes manual
    release detail/draft rows and any release rows without a Discogs id before
    restoring that constraint.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "releases",
        sa.Column("source", sa.String(length=20), server_default="DISCOGS", nullable=False),
    )
    op.alter_column("releases", "discogs_release_id", existing_type=sa.BigInteger(), nullable=True)
    op.create_check_constraint("ck_releases_source", "releases", "source IN ('DISCOGS', 'MANUAL')")
    op.create_check_constraint(
        "ck_releases_discogs_id_required_for_discogs",
        "releases",
        "(source != 'DISCOGS') OR (discogs_release_id IS NOT NULL)",
    )

    op.create_table(
        "manual_release_details",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("release_id", sa.String(), nullable=False),
        sa.Column("artists", sa.JSON(), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("identifiers", sa.JSON(), nullable=False),
        sa.Column("format_details", sa.JSON(), nullable=False),
        sa.Column("tracklist", sa.JSON(), nullable=False),
        sa.Column("cover_storage_key", sa.String(), nullable=True),
        sa.Column("cover_image_url", sa.String(), nullable=True),
        sa.Column("cover_thumbnail_url", sa.String(), nullable=True),
        sa.Column("cover_content_type", sa.String(length=80), nullable=True),
        sa.Column("cover_size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "cover_size_bytes IS NULL OR cover_size_bytes >= 0",
            name="ck_manual_release_details_cover_size_non_negative",
        ),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", name="uq_manual_release_details_release_id"),
    )
    op.create_index(
        "idx_manual_release_details_release_id",
        "manual_release_details",
        ["release_id"],
    )

    op.create_table(
        "manual_release_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("form_data", sa.JSON(), nullable=False),
        sa.Column("completion_state", sa.JSON(), nullable=True),
        sa.Column("cover_storage_key", sa.String(), nullable=True),
        sa.Column("cover_image_url", sa.String(), nullable=True),
        sa.Column("cover_thumbnail_url", sa.String(), nullable=True),
        sa.Column("cover_content_type", sa.String(length=80), nullable=True),
        sa.Column("cover_size_bytes", sa.Integer(), nullable=True),
        sa.Column("validation_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "cover_size_bytes IS NULL OR cover_size_bytes >= 0",
            name="ck_manual_release_drafts_cover_size_non_negative",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_manual_release_drafts_user_id", "manual_release_drafts", ["user_id"])
    op.create_index(
        "idx_manual_release_drafts_user_updated",
        "manual_release_drafts",
        ["user_id", "updated_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_manual_release_drafts_user_updated", table_name="manual_release_drafts")
    op.drop_index("idx_manual_release_drafts_user_id", table_name="manual_release_drafts")
    op.drop_table("manual_release_drafts")
    op.drop_index("idx_manual_release_details_release_id", table_name="manual_release_details")
    op.drop_table("manual_release_details")

    op.drop_constraint("ck_releases_discogs_id_required_for_discogs", "releases", type_="check")
    op.drop_constraint("ck_releases_source", "releases", type_="check")
    op.execute("""
        DELETE FROM sessions
        WHERE release_id IN (
            SELECT id FROM releases WHERE discogs_release_id IS NULL
        )
        """)
    op.execute("DELETE FROM releases WHERE discogs_release_id IS NULL")
    op.alter_column("releases", "discogs_release_id", existing_type=sa.BigInteger(), nullable=False)
    op.drop_column("releases", "source")
