"""add identify job stale recovery index

Revision ID: d2b8c7e9f041
Revises: 7ab6c5d4e3f2
Create Date: 2026-05-15 20:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2b8c7e9f041"
down_revision: str | Sequence[str] | None = "7ab6c5d4e3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("idx_identify_jobs_status_updated_at", "identify_jobs", ["status", "updated_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_identify_jobs_status_updated_at", table_name="identify_jobs")
