"""add user collection scope

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-06-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "release_collection_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("release_id", sa.String(), nullable=False),
        sa.Column("in_collection", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("collection_added_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collection_removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_discogs_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discogs_instance_id", sa.BigInteger(), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "release_id", name="uq_release_collection_membership_user_release"),
    )
    op.create_index(
        "idx_release_collection_memberships_user_active",
        "release_collection_memberships",
        ["user_id", "in_collection"],
    )
    op.create_index(
        "idx_release_collection_memberships_user_favorite",
        "release_collection_memberships",
        ["user_id", "is_favorite"],
    )
    op.create_index(
        "idx_release_collection_memberships_user_added",
        "release_collection_memberships",
        ["user_id", "collection_added_at"],
    )

    op.add_column("collection_folders", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_collection_folders_user_id_user_accounts",
        "collection_folders",
        "user_accounts",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("idx_collection_folders_discogs_folder_id", table_name="collection_folders")
    op.drop_index("idx_collection_folders_is_default", table_name="collection_folders")
    op.drop_constraint("collection_folders_discogs_folder_id_key", "collection_folders", type_="unique")
    op.create_unique_constraint(
        "uq_collection_folders_user_discogs_folder",
        "collection_folders",
        ["user_id", "discogs_folder_id"],
    )
    op.create_index(
        "idx_collection_folders_user_discogs_folder_id",
        "collection_folders",
        ["user_id", "discogs_folder_id"],
    )
    op.create_index("idx_collection_folders_user_is_default", "collection_folders", ["user_id", "is_default"])

    op.add_column("release_collection_folders", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_release_collection_folders_user_id_user_accounts",
        "release_collection_folders",
        "user_accounts",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("idx_release_collection_folders_folder_id", table_name="release_collection_folders")
    op.drop_index("idx_release_collection_folders_release_id", table_name="release_collection_folders")
    op.drop_constraint("uq_release_collection_folder", "release_collection_folders", type_="unique")
    op.create_unique_constraint(
        "uq_release_collection_folder_user",
        "release_collection_folders",
        ["user_id", "release_id", "collection_folder_id"],
    )
    op.create_index(
        "idx_release_collection_folders_user_release_id",
        "release_collection_folders",
        ["user_id", "release_id"],
    )
    op.create_index(
        "idx_release_collection_folders_user_folder_id",
        "release_collection_folders",
        ["user_id", "collection_folder_id"],
    )

    op.add_column("collection_sync_jobs", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_collection_sync_jobs_user_id_user_accounts",
        "collection_sync_jobs",
        "user_accounts",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_collection_sync_jobs_user_status", "collection_sync_jobs", ["user_id", "status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_collection_sync_jobs_user_status", table_name="collection_sync_jobs")
    op.drop_constraint("fk_collection_sync_jobs_user_id_user_accounts", "collection_sync_jobs", type_="foreignkey")
    op.drop_column("collection_sync_jobs", "user_id")

    op.drop_index("idx_release_collection_folders_user_folder_id", table_name="release_collection_folders")
    op.drop_index("idx_release_collection_folders_user_release_id", table_name="release_collection_folders")
    op.drop_constraint("uq_release_collection_folder_user", "release_collection_folders", type_="unique")
    op.create_unique_constraint(
        "uq_release_collection_folder",
        "release_collection_folders",
        ["release_id", "collection_folder_id"],
    )
    op.create_index(
        "idx_release_collection_folders_release_id",
        "release_collection_folders",
        ["release_id"],
    )
    op.create_index(
        "idx_release_collection_folders_folder_id",
        "release_collection_folders",
        ["collection_folder_id"],
    )
    op.drop_constraint(
        "fk_release_collection_folders_user_id_user_accounts",
        "release_collection_folders",
        type_="foreignkey",
    )
    op.drop_column("release_collection_folders", "user_id")

    op.drop_index("idx_collection_folders_user_is_default", table_name="collection_folders")
    op.drop_index("idx_collection_folders_user_discogs_folder_id", table_name="collection_folders")
    op.drop_constraint("uq_collection_folders_user_discogs_folder", "collection_folders", type_="unique")
    op.create_unique_constraint("collection_folders_discogs_folder_id_key", "collection_folders", ["discogs_folder_id"])
    op.create_index("idx_collection_folders_is_default", "collection_folders", ["is_default"])
    op.create_index("idx_collection_folders_discogs_folder_id", "collection_folders", ["discogs_folder_id"])
    op.drop_constraint("fk_collection_folders_user_id_user_accounts", "collection_folders", type_="foreignkey")
    op.drop_column("collection_folders", "user_id")

    op.drop_index("idx_release_collection_memberships_user_added", table_name="release_collection_memberships")
    op.drop_index("idx_release_collection_memberships_user_favorite", table_name="release_collection_memberships")
    op.drop_index("idx_release_collection_memberships_user_active", table_name="release_collection_memberships")
    op.drop_table("release_collection_memberships")
