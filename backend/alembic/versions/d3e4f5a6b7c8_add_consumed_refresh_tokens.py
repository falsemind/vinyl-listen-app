"""add consumed refresh tokens

Revision ID: d3e4f5a6b7c8
Revises: c2f3a4b5d6e7
Create Date: 2026-06-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: str | Sequence[str] | None = "c2f3a4b5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "consumed_refresh_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["auth_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_consumed_refresh_tokens_hash"),
    )
    op.create_index("idx_consumed_refresh_tokens_session_id", "consumed_refresh_tokens", ["session_id"])
    op.create_index("idx_consumed_refresh_tokens_user_id", "consumed_refresh_tokens", ["user_id"])
    op.create_index(
        "idx_consumed_refresh_tokens_refresh_token_hash",
        "consumed_refresh_tokens",
        ["refresh_token_hash"],
    )
    op.create_index("idx_consumed_refresh_tokens_expires_at", "consumed_refresh_tokens", ["expires_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_consumed_refresh_tokens_expires_at", table_name="consumed_refresh_tokens")
    op.drop_index("idx_consumed_refresh_tokens_refresh_token_hash", table_name="consumed_refresh_tokens")
    op.drop_index("idx_consumed_refresh_tokens_user_id", table_name="consumed_refresh_tokens")
    op.drop_index("idx_consumed_refresh_tokens_session_id", table_name="consumed_refresh_tokens")
    op.drop_table("consumed_refresh_tokens")
