from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SessionsMoods(Base):
    """SQLAlchemy model for the session_moods table.

    Represents a mood that can be selected during a listening session. The
    ``user_id`` is null for shared reference rows and populated for user-owned
    custom moods.
    """

    __tablename__ = "session_moods"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_session_moods_user_name"),
        Index("idx_session_moods_user_custom", "user_id", "is_custom"),
    )

    # Primary key – a UUID stored as a string.
    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Owner for custom moods. Null means shared reference data.
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Mood label.
    name: Mapped[str] = mapped_column(String, nullable=False)

    # Indicates if this mood was defined by a user.
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamp when the mood was created.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
