"""add user collection scope

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-06-18 00:00:00.000000

"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_OWNER_EMAIL_ENV = "VINYL_LEGACY_OWNER_EMAIL"


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

    legacy_owner_id = None
    if not context.is_offline_mode():
        bind = op.get_bind()
        legacy_owner_id = _resolve_legacy_owner_id(bind)
        if legacy_owner_id is not None:
            _backfill_legacy_collection_memberships(bind, legacy_owner_id=legacy_owner_id)

    op.add_column("collection_folders", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_collection_folders_user_id_user_accounts",
        "collection_folders",
        "user_accounts",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    if legacy_owner_id is not None:
        bind = op.get_bind()
        _backfill_legacy_owner_column(bind, table_name="collection_folders", legacy_owner_id=legacy_owner_id)
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
    if legacy_owner_id is not None:
        bind = op.get_bind()
        _backfill_legacy_owner_column(bind, table_name="release_collection_folders", legacy_owner_id=legacy_owner_id)
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
    if legacy_owner_id is not None:
        bind = op.get_bind()
        _backfill_legacy_owner_column(bind, table_name="collection_sync_jobs", legacy_owner_id=legacy_owner_id)
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


def _resolve_legacy_owner_id(bind: Connection) -> str | None:
    if not _has_legacy_collection_scope_rows(bind):
        return None

    owner_email = os.getenv(LEGACY_OWNER_EMAIL_ENV)
    if owner_email and owner_email.strip():
        owner_id = bind.execute(
            sa.text("""
                SELECT id
                FROM user_accounts
                WHERE normalized_email = :normalized_email
                  AND is_active = TRUE
                  AND deleted_at IS NULL
                """),
            {"normalized_email": owner_email.strip().lower()},
        ).scalar_one_or_none()
        if owner_id is None:
            raise RuntimeError(
                f"{LEGACY_OWNER_EMAIL_ENV} does not match an active account. "
                "Set it to the existing account email before upgrading legacy collection data."
            )
        return str(owner_id)

    owner_ids = [str(row[0]) for row in bind.execute(sa.text("""
                SELECT id
                FROM user_accounts
                WHERE is_active = TRUE
                  AND deleted_at IS NULL
                ORDER BY created_at ASC, id ASC
                """)).all()]
    if len(owner_ids) == 1:
        return owner_ids[0]

    if not owner_ids:
        raise RuntimeError(
            "Legacy collection data exists but no active account is available. "
            "Create/register the owner account before upgrading, or reset local collection data."
        )

    raise RuntimeError(
        "Legacy collection data exists but multiple active accounts are available. "
        f"Set {LEGACY_OWNER_EMAIL_ENV} to the intended owner email before upgrading."
    )


def _has_legacy_collection_scope_rows(bind: Connection) -> bool:
    return bool(bind.execute(sa.text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM releases
                    WHERE in_collection = TRUE
                       OR collection_added_at IS NOT NULL
                       OR collection_removed_at IS NOT NULL
                       OR last_discogs_sync_at IS NOT NULL
                       OR discogs_instance_id IS NOT NULL
                       OR is_favorite = TRUE
                )
                OR EXISTS (SELECT 1 FROM collection_folders)
                OR EXISTS (SELECT 1 FROM release_collection_folders)
                OR EXISTS (SELECT 1 FROM collection_sync_jobs)
                """)).scalar())


def _backfill_legacy_collection_memberships(bind: Connection, *, legacy_owner_id: str) -> None:
    bind.execute(
        sa.text("""
            INSERT INTO release_collection_memberships (
                user_id,
                release_id,
                in_collection,
                collection_added_at,
                collection_removed_at,
                last_discogs_sync_at,
                discogs_instance_id,
                is_favorite,
                created_at,
                updated_at
            )
            SELECT
                :legacy_owner_id,
                releases.id,
                releases.in_collection,
                releases.collection_added_at,
                releases.collection_removed_at,
                releases.last_discogs_sync_at,
                releases.discogs_instance_id,
                releases.is_favorite,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM releases
            WHERE (
                releases.in_collection = TRUE
                OR releases.collection_added_at IS NOT NULL
                OR releases.collection_removed_at IS NOT NULL
                OR releases.last_discogs_sync_at IS NOT NULL
                OR releases.discogs_instance_id IS NOT NULL
                OR releases.is_favorite = TRUE
            )
            AND NOT EXISTS (
                SELECT 1
                FROM release_collection_memberships existing
                WHERE existing.user_id = :legacy_owner_id
                  AND existing.release_id = releases.id
            )
            """),
        {"legacy_owner_id": legacy_owner_id},
    )


def _backfill_legacy_owner_column(bind: Connection, *, table_name: str, legacy_owner_id: str) -> None:
    if table_name not in {"collection_folders", "release_collection_folders", "collection_sync_jobs"}:
        raise ValueError(f"Unsupported legacy owner table: {table_name}")

    bind.execute(
        sa.text(f"UPDATE {table_name} SET user_id = :legacy_owner_id WHERE user_id IS NULL"),
        {"legacy_owner_id": legacy_owner_id},
    )
