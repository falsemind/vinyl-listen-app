"""add release favorites

Revision ID: 5f1a2b3c4d6e
Revises: 3d9f1a2b4c6e
Create Date: 2026-06-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5f1a2b3c4d6e"
down_revision: str | Sequence[str] | None = "3d9f1a2b4c6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "releases",
        sa.Column("is_favorite", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index("idx_releases_is_favorite", "releases", ["is_favorite"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_releases_is_favorite", table_name="releases")
    op.drop_column("releases", "is_favorite")
