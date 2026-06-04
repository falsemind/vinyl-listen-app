"""add collection sync jobs

Revision ID: f7c8d9e0a123
Revises: e6a7b8c9d012
Create Date: 2026-06-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7c8d9e0a123"
down_revision: str | Sequence[str] | None = "e6a7b8c9d012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("releases", sa.Column("format", sa.String(), nullable=True))
    op.add_column("releases", sa.Column("thumbnail_url", sa.String(), nullable=True))

    op.create_table(
        "collection_sync_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("step", sa.String(length=40), nullable=True),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("processed_items", sa.Integer(), nullable=False),
        sa.Column("added_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("removed_count", sa.Integer(), nullable=False),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_collection_sync_jobs_status", "collection_sync_jobs", ["status"])
    op.create_index(
        "idx_collection_sync_jobs_status_updated_at",
        "collection_sync_jobs",
        ["status", "updated_at"],
    )
    op.create_index("idx_collection_sync_jobs_expires_at", "collection_sync_jobs", ["expires_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_collection_sync_jobs_expires_at", table_name="collection_sync_jobs")
    op.drop_index("idx_collection_sync_jobs_status_updated_at", table_name="collection_sync_jobs")
    op.drop_index("idx_collection_sync_jobs_status", table_name="collection_sync_jobs")
    op.drop_table("collection_sync_jobs")
    op.drop_column("releases", "thumbnail_url")
    op.drop_column("releases", "format")
