from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base

json_type = JSONB().with_variant(JSON(), "sqlite")


class SpotifyListeningImportBatch(Base):
    """Metadata and counts for a local Spotify listening-history import."""

    __tablename__ = "spotify_listening_import_batches"
    __table_args__ = (
        Index("idx_spotify_import_batches_status", "status"),
        Index("idx_spotify_import_batches_started_at", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_paths: Mapped[list[str]] = mapped_column(json_type, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[list[str] | None] = mapped_column(json_type, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SpotifyListeningEvent(Base):
    """Filtered Spotify song play event retained for local AI insight analytics."""

    __tablename__ = "spotify_listening_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_spotify_listening_events_event_key"),
        Index("idx_spotify_events_played_at", "played_at"),
        Index("idx_spotify_events_played_date", "played_date"),
        Index("idx_spotify_events_artist", "normalized_artist_name"),
        Index("idx_spotify_events_album", "normalized_album_name"),
        Index("idx_spotify_events_track", "normalized_track_name"),
        Index("idx_spotify_events_year_month_artist", "played_year_month", "normalized_artist_name"),
        Index("idx_spotify_events_meaningful", "is_meaningful_listen"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    import_batch_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("spotify_listening_import_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    played_date: Mapped[date] = mapped_column(Date, nullable=False)
    played_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    played_weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    played_year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    ms_played: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conn_country: Mapped[str | None] = mapped_column(String(16), nullable=True)
    track_name: Mapped[str] = mapped_column(String(512), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    album_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    normalized_track_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_album_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reason_start: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_end: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shuffle: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    skipped: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    offline: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    offline_timestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_meaningful_listen: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
