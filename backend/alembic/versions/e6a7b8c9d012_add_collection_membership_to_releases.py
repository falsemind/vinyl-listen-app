"""add collection membership to releases

Revision ID: e6a7b8c9d012
Revises: 9c6e2a1f4b80
Create Date: 2026-06-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6a7b8c9d012"
down_revision: str | Sequence[str] | None = "9c6e2a1f4b80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "releases",
        sa.Column("in_collection", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("releases", sa.Column("collection_added_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("releases", sa.Column("collection_removed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("releases", sa.Column("last_discogs_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("releases", sa.Column("discogs_instance_id", sa.BigInteger(), nullable=True))
    op.create_index("idx_releases_in_collection", "releases", ["in_collection"])
    op.create_index("idx_releases_collection_added_at", "releases", ["collection_added_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_releases_collection_added_at", table_name="releases")
    op.drop_index("idx_releases_in_collection", table_name="releases")
    op.drop_column("releases", "discogs_instance_id")
    op.drop_column("releases", "last_discogs_sync_at")
    op.drop_column("releases", "collection_removed_at")
    op.drop_column("releases", "collection_added_at")
    op.drop_column("releases", "in_collection")
