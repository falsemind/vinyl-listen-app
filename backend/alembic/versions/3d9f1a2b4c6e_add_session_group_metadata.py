"""add session group metadata

Revision ID: 3d9f1a2b4c6e
Revises: 8c1d2e3f4a5b
Create Date: 2026-06-12 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "3d9f1a2b4c6e"
down_revision: str | Sequence[str] | None = "8c1d2e3f4a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("session_groups") as batch_op:
        batch_op.add_column(
            sa.Column("style_focus", sa.String(), server_default="mixed", nullable=False),
        )
        batch_op.add_column(
            sa.Column("mood_direction", sa.String(), server_default="steady_mood", nullable=False),
        )
        batch_op.add_column(
            sa.Column("session_type", sa.String(), server_default="casual_listening", nullable=False),
        )
        batch_op.add_column(sa.Column("notes", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("session_groups") as batch_op:
        batch_op.drop_column("notes")
        batch_op.drop_column("session_type")
        batch_op.drop_column("mood_direction")
        batch_op.drop_column("style_focus")
