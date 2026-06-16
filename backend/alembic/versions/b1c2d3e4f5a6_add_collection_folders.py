"""add collection folders

Revision ID: b1c2d3e4f5a6
Revises: ab12cd34ef56
Create Date: 2026-06-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "ab12cd34ef56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "collection_folders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("discogs_folder_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_discogs_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discogs_folder_id"),
    )
    op.create_index(
        "idx_collection_folders_discogs_folder_id",
        "collection_folders",
        ["discogs_folder_id"],
    )
    op.create_index("idx_collection_folders_is_default", "collection_folders", ["is_default"])

    op.create_table(
        "release_collection_folders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.String(), nullable=False),
        sa.Column("collection_folder_id", sa.Integer(), nullable=False),
        sa.Column("discogs_instance_id", sa.BigInteger(), nullable=True),
        sa.Column("date_added", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_discogs_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["collection_folder_id"], ["collection_folders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "collection_folder_id", name="uq_release_collection_folder"),
    )
    op.create_index(
        "idx_release_collection_folders_folder_id",
        "release_collection_folders",
        ["collection_folder_id"],
    )
    op.create_index(
        "idx_release_collection_folders_release_id",
        "release_collection_folders",
        ["release_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_release_collection_folders_release_id", table_name="release_collection_folders")
    op.drop_index("idx_release_collection_folders_folder_id", table_name="release_collection_folders")
    op.drop_table("release_collection_folders")
    op.drop_index("idx_collection_folders_is_default", table_name="collection_folders")
    op.drop_index("idx_collection_folders_discogs_folder_id", table_name="collection_folders")
    op.drop_table("collection_folders")
