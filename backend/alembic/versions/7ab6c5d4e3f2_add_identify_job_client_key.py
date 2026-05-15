"""add identify job client key

Revision ID: 7ab6c5d4e3f2
Revises: b7f3c9d2a4e1
Create Date: 2026-05-15 16:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7ab6c5d4e3f2"
down_revision: str | Sequence[str] | None = "b7f3c9d2a4e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("identify_jobs", sa.Column("client_key", sa.String(length=255), nullable=True))
    op.create_index("idx_identify_jobs_client_key_status", "identify_jobs", ["client_key", "status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_identify_jobs_client_key_status", table_name="identify_jobs")
    op.drop_column("identify_jobs", "client_key")
