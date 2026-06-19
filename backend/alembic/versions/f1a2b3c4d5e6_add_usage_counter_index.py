"""add usage counter index

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-06-19 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "idx_usage_events_user_capability_time",
        "usage_events",
        ["user_id", "capability", "occurred_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_usage_events_user_capability_time", table_name="usage_events")
