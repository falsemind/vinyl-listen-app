"""add session user scope

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-06-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6b7c8d9e0f1"
down_revision: str | Sequence[str] | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("session_groups", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_session_groups_user_id_user_accounts",
        "session_groups",
        "user_accounts",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_session_groups_user_id", "session_groups", ["user_id"])
    op.create_index("idx_session_groups_user_status", "session_groups", ["user_id", "status"])

    op.add_column("sessions", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_sessions_user_id_user_accounts",
        "sessions",
        "user_accounts",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_index("idx_sessions_user_release_id", "sessions", ["user_id", "release_id"])
    op.create_index("idx_sessions_user_played_at", "sessions", ["user_id", "played_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_sessions_user_played_at", table_name="sessions")
    op.drop_index("idx_sessions_user_release_id", table_name="sessions")
    op.drop_index("idx_sessions_user_id", table_name="sessions")
    op.drop_constraint("fk_sessions_user_id_user_accounts", "sessions", type_="foreignkey")
    op.drop_column("sessions", "user_id")

    op.drop_index("idx_session_groups_user_status", table_name="session_groups")
    op.drop_index("idx_session_groups_user_id", table_name="session_groups")
    op.drop_constraint("fk_session_groups_user_id_user_accounts", "session_groups", type_="foreignkey")
    op.drop_column("session_groups", "user_id")
