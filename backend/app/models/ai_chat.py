from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base

json_type = JSONB().with_variant(JSON(), "sqlite")


class AiChatSession(Base):
    """Persisted AI chat conversation."""

    __tablename__ = "ai_chat_sessions"
    __table_args__ = (Index("idx_ai_chat_sessions_updated_at", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AiChatMessageRecord(Base):
    """Persisted user or assistant message for an AI chat conversation."""

    __tablename__ = "ai_chat_messages"
    __table_args__ = (
        Index("idx_ai_chat_messages_conversation_created", "conversation_id", "created_at"),
        Index("idx_ai_chat_messages_conversation_role", "conversation_id", "role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    used_tools: Mapped[list[str] | None] = mapped_column(json_type, nullable=True)
    client_context: Mapped[dict | None] = mapped_column(json_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
