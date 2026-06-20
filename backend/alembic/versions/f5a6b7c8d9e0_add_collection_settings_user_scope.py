"""add collection settings user scope

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: str | Sequence[str] | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("collection_settings", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_index("idx_collection_settings_user_id", "collection_settings", ["user_id"])
    op.create_unique_constraint("uq_collection_settings_user_id", "collection_settings", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_collection_settings_user_id", "collection_settings", type_="unique")
    op.drop_index("idx_collection_settings_user_id", table_name="collection_settings")
    op.drop_column("collection_settings", "user_id")
