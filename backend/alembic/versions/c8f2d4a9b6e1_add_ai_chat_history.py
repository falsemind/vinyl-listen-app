"""add AI chat history tables

Revision ID: c8f2d4a9b6e1
Revises: f3a4b5c6d7e8
Create Date: 2026-05-23 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8f2d4a9b6e1"
down_revision: str | Sequence[str] | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ai_chat_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ai_chat_sessions_updated_at", "ai_chat_sessions", ["updated_at"])

    op.create_table(
        "ai_chat_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("used_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("client_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_chat_sessions.id"],
            name="fk_ai_chat_messages_conversation_id_ai_chat_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ai_chat_messages_conversation_created",
        "ai_chat_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "idx_ai_chat_messages_conversation_role",
        "ai_chat_messages",
        ["conversation_id", "role"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_ai_chat_messages_conversation_role", table_name="ai_chat_messages")
    op.drop_index("idx_ai_chat_messages_conversation_created", table_name="ai_chat_messages")
    op.drop_table("ai_chat_messages")
    op.drop_index("idx_ai_chat_sessions_updated_at", table_name="ai_chat_sessions")
    op.drop_table("ai_chat_sessions")
