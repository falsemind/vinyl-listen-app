from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SessionsMoods(Base):
    """SQLAlchemy model for the session_moods table.

    Represents a mood that can be selected during a listening session. The
    ``name`` field is unique, and ``is_custom`` indicates whether the mood was
    added by a user.
    """

    __tablename__ = "session_moods"

    # Primary key – a UUID stored as a string.
    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Mood label – unique.
    name: Mapped[str] = mapped_column(String, nullable=False)

    # Indicates if this mood was defined by a user.
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamp when the mood was created.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
