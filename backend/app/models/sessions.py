from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Sessions(Base):
    """SQLAlchemy model for the sessions table.

    The columns map directly to the database schema described in
    ``docs/architecture/database-schema.md``.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_release_id", "release_id"),
        Index("idx_sessions_played_at", "played_at"),
    )

    # Primary key – a UUID stored as a string.
    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign key to releases table.
    release_id: Mapped[str] = mapped_column(String, ForeignKey("releases.id"), nullable=False)

    # Optional rating (1-5).
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Mood selected by the user – stored as a string.
    mood: Mapped[str | None] = mapped_column(String, nullable=True)

    # Optional session notes.
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # Time of listening.
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optional vinyl side (A, B, C...).
    vinyl_side: Mapped[str | None] = mapped_column(String, nullable=True)

    # Timestamp when the session record was created.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionTracks(Base):
    """Optional Discogs track selections attached to a side-level session."""

    __tablename__ = "session_tracks"
    __table_args__ = (
        Index("idx_session_tracks_session_id", "session_id"),
        Index("idx_session_tracks_track_position", "track_position"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    track_position: Mapped[str] = mapped_column(String, nullable=False)
    track_title: Mapped[str] = mapped_column(String, nullable=False)
    track_duration: Mapped[str | None] = mapped_column(String, nullable=True)
    track_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
