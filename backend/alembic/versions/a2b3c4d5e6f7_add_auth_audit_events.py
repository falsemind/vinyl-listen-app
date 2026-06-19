"""add auth audit events

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "auth_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_auth_audit_events_user_id", "auth_audit_events", ["user_id"])
    op.create_index("idx_auth_audit_events_session_id", "auth_audit_events", ["session_id"])
    op.create_index("idx_auth_audit_events_occurred_at", "auth_audit_events", ["occurred_at"])
    op.create_index("idx_auth_audit_events_user_time", "auth_audit_events", ["user_id", "occurred_at"])
    op.create_index(
        "idx_auth_audit_events_event_type_time",
        "auth_audit_events",
        ["event_type", "occurred_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_auth_audit_events_event_type_time", table_name="auth_audit_events")
    op.drop_index("idx_auth_audit_events_user_time", table_name="auth_audit_events")
    op.drop_index("idx_auth_audit_events_occurred_at", table_name="auth_audit_events")
    op.drop_index("idx_auth_audit_events_session_id", table_name="auth_audit_events")
    op.drop_index("idx_auth_audit_events_user_id", table_name="auth_audit_events")
    op.drop_table("auth_audit_events")
