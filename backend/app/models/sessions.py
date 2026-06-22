from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SessionGroups(Base):
    """SQLAlchemy model for optional timed listening session groups."""

    __tablename__ = "session_groups"
    __table_args__ = (
        Index("idx_session_groups_user_id", "user_id"),
        Index("idx_session_groups_user_status", "user_id", "status"),
        Index("idx_session_groups_status", "status"),
        Index("idx_session_groups_started_at", "started_at"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="active", server_default="active")
    style_focus: Mapped[str] = mapped_column(String, nullable=False, default="mixed", server_default="mixed")
    mood_direction: Mapped[str] = mapped_column(
        String, nullable=False, default="steady_mood", server_default="steady_mood"
    )
    session_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="casual_listening",
        server_default="casual_listening",
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Sessions(Base):
    """SQLAlchemy model for the sessions table.

    The columns map directly to the database schema described in
    ``docs/architecture/database-schema.md``.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "(release_id IS NOT NULL AND manual_release_id IS NULL) "
            "OR (release_id IS NULL AND manual_release_id IS NOT NULL)",
            name="ck_sessions_exactly_one_release_target",
        ),
        Index("idx_sessions_user_id", "user_id"),
        Index("idx_sessions_user_release_id", "user_id", "release_id"),
        Index("idx_sessions_user_manual_release_id", "user_id", "manual_release_id"),
        Index("idx_sessions_user_played_at", "user_id", "played_at"),
        Index("idx_sessions_release_id", "release_id"),
        Index("idx_sessions_manual_release_id", "manual_release_id"),
        Index("idx_sessions_played_at", "played_at"),
        Index("idx_sessions_session_group_id", "session_group_id"),
    )

    # Primary key – a UUID stored as a string.
    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign key to shared Discogs-backed releases table.
    release_id: Mapped[str | None] = mapped_column(String, ForeignKey("releases.id"), nullable=True)

    # Foreign key to user-owned manual releases table.
    manual_release_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("manual_releases.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Owner account for multi-user data isolation. Nullable only for legacy rows before backfill.
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Optional parent timed listening session group.
    session_group_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("session_groups.id", ondelete="SET NULL"),
        nullable=True,
    )

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
    track_artist: Mapped[str | None] = mapped_column(String, nullable=True)
    track_title: Mapped[str] = mapped_column(String, nullable=False)
    track_duration: Mapped[str | None] = mapped_column(String, nullable=True)
    track_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
