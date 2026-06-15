"""add collection settings

Revision ID: 6b7c8d9e0f12
Revises: 5f1a2b3c4d6e
Create Date: 2026-06-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b7c8d9e0f12"
down_revision: str | Sequence[str] | None = "5f1a2b3c4d6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "collection_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_of_truth", sa.String(length=20), server_default="APP", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_of_truth IN ('APP', 'DISCOGS')", name="ck_collection_settings_source_of_truth"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO collection_settings (id, source_of_truth) VALUES (1, 'APP')")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("collection_settings")
