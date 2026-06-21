"""add manual release schema

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-21 00:00:00.000000

Rollback note:
    Manual release rows are user-owned app data and are intentionally not part
    of the shared Discogs-backed ``releases`` catalog. Downgrading drops manual
    release and draft rows without changing shared release metadata.

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
    op.create_table(
        "manual_releases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("artist", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("catalog_number", sa.String(length=80), nullable=True),
        sa.Column("barcode", sa.String(length=14), nullable=True),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("genres", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("styles", sa.ARRAY(sa.String()), nullable=True),
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
        sa.Column("in_collection", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("collection_added_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collection_removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "cover_size_bytes IS NULL OR cover_size_bytes >= 0",
            name="ck_manual_releases_cover_size_non_negative",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_manual_releases_user_id", "manual_releases", ["user_id"])
    op.create_index("idx_manual_releases_user_updated", "manual_releases", ["user_id", "updated_at"])
    op.create_index("idx_manual_releases_user_title", "manual_releases", ["user_id", "title"])
    op.create_index("idx_manual_releases_in_collection", "manual_releases", ["in_collection"])

    op.create_table(
        "manual_release_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
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
    op.drop_index("idx_manual_releases_in_collection", table_name="manual_releases")
    op.drop_index("idx_manual_releases_user_title", table_name="manual_releases")
    op.drop_index("idx_manual_releases_user_updated", table_name="manual_releases")
    op.drop_index("idx_manual_releases_user_id", table_name="manual_releases")
    op.drop_table("manual_releases")
