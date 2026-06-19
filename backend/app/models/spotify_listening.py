from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base

json_type = JSONB().with_variant(JSON(), "sqlite")


class SpotifyListeningImportBatch(Base):
    """Metadata and counts for a local Spotify listening-history import."""

    __tablename__ = "spotify_listening_import_batches"
    __table_args__ = (
        Index("idx_spotify_import_batches_user_status", "user_id", "status"),
        Index("idx_spotify_import_batches_status", "status"),
        Index("idx_spotify_import_batches_user_started_at", "user_id", "started_at"),
        Index("idx_spotify_import_batches_started_at", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
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
        UniqueConstraint("user_id", "event_key", name="uq_spotify_listening_events_user_event_key"),
        Index("idx_spotify_events_user_played_at", "user_id", "played_at"),
        Index("idx_spotify_events_played_at", "played_at"),
        Index("idx_spotify_events_played_date", "played_date"),
        Index("idx_spotify_events_user_artist", "user_id", "normalized_artist_name"),
        Index("idx_spotify_events_artist", "normalized_artist_name"),
        Index("idx_spotify_events_album", "normalized_album_name"),
        Index("idx_spotify_events_track", "normalized_track_name"),
        Index("idx_spotify_events_user_year_month_artist", "user_id", "played_year_month", "normalized_artist_name"),
        Index("idx_spotify_events_year_month_artist", "played_year_month", "normalized_artist_name"),
        Index("idx_spotify_events_meaningful", "is_meaningful_listen"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
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


class SpotifyArtistStats(Base):
    """Aggregated Spotify listening stats by normalized artist."""

    __tablename__ = "spotify_artist_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_artist_name", name="uq_spotify_artist_stats_user_artist"),
        Index("idx_spotify_artist_stats_user_total_ms", "user_id", "total_ms_played"),
        Index("idx_spotify_artist_stats_total_ms", "total_ms_played"),
    )

    stat_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    normalized_artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    meaningful_play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_ms_played: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SpotifyAlbumStats(Base):
    """Aggregated Spotify listening stats by normalized artist and album."""

    __tablename__ = "spotify_album_stats"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "normalized_artist_name",
            "normalized_album_name",
            name="uq_spotify_album_stats_user_artist_album",
        ),
        Index("idx_spotify_album_stats_user_artist", "user_id", "normalized_artist_name"),
        Index("idx_spotify_album_stats_artist", "normalized_artist_name"),
        Index("idx_spotify_album_stats_user_total_ms", "user_id", "total_ms_played"),
        Index("idx_spotify_album_stats_total_ms", "total_ms_played"),
    )

    stat_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    normalized_artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_album_name: Mapped[str] = mapped_column(String(512), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    album_name: Mapped[str] = mapped_column(String(512), nullable=False)
    play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    meaningful_play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_ms_played: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SpotifyTrackStats(Base):
    """Aggregated Spotify listening stats by normalized artist, album, and track."""

    __tablename__ = "spotify_track_stats"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "normalized_artist_name",
            "normalized_album_name",
            "normalized_track_name",
            name="uq_spotify_track_stats_user_artist_album_track",
        ),
        Index("idx_spotify_track_stats_user_artist", "user_id", "normalized_artist_name"),
        Index("idx_spotify_track_stats_artist", "normalized_artist_name"),
        Index("idx_spotify_track_stats_user_total_ms", "user_id", "total_ms_played"),
        Index("idx_spotify_track_stats_total_ms", "total_ms_played"),
    )

    stat_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    normalized_artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_album_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    normalized_track_name: Mapped[str] = mapped_column(String(512), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    album_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    track_name: Mapped[str] = mapped_column(String(512), nullable=False)
    play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    meaningful_play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_ms_played: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SpotifyHourlyStats(Base):
    """Aggregated Spotify listening stats by played hour."""

    __tablename__ = "spotify_hourly_stats"
    __table_args__ = (UniqueConstraint("user_id", "played_hour", name="uq_spotify_hourly_stats_user_hour"),)

    stat_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    played_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    meaningful_play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_ms_played: Mapped[int] = mapped_column(BigInteger, nullable=False)


class SpotifyMonthlyArtistStats(Base):
    """Aggregated Spotify listening stats by month and normalized artist."""

    __tablename__ = "spotify_monthly_artist_stats"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "played_year_month",
            "normalized_artist_name",
            name="uq_spotify_monthly_artist_stats_user_month_artist",
        ),
        Index("idx_spotify_monthly_artist_stats_user_artist", "user_id", "normalized_artist_name"),
        Index("idx_spotify_monthly_artist_stats_artist", "normalized_artist_name"),
        Index("idx_spotify_monthly_artist_stats_user_month", "user_id", "played_year_month"),
        Index("idx_spotify_monthly_artist_stats_month", "played_year_month"),
    )

    stat_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    played_year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    normalized_artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    meaningful_play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_ms_played: Mapped[int] = mapped_column(BigInteger, nullable=False)


class SpotifySkipStats(Base):
    """Aggregated Spotify skip/end-reason stats."""

    __tablename__ = "spotify_skip_stats"

    stat_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    skipped: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reason_end: Mapped[str | None] = mapped_column(String(64), nullable=True)
    play_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_ms_played: Mapped[int] = mapped_column(BigInteger, nullable=False)


class SpotifyVinylArtistMatch(Base):
    """Exact normalized artist overlap between Spotify history and known vinyl releases."""

    __tablename__ = "spotify_vinyl_artist_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_artist_name", name="uq_spotify_vinyl_artist_matches_user_artist"),
        Index("idx_spotify_vinyl_artist_matches_user_confidence", "user_id", "confidence_score"),
        Index("idx_spotify_vinyl_artist_matches_confidence", "confidence_score"),
    )

    match_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    normalized_artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    release_ids: Mapped[list[str]] = mapped_column(json_type, nullable=False)
    release_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    match_type: Mapped[str] = mapped_column(String(40), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)


class SpotifyVinylReleaseMatch(Base):
    """Exact normalized album/release overlap between Spotify history and known vinyl releases."""

    __tablename__ = "spotify_vinyl_release_matches"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "release_id",
            "normalized_artist_name",
            "normalized_album_name",
            name="uq_spotify_release_match_user_release_artist_album",
        ),
        Index("idx_spotify_vinyl_release_matches_user_artist", "user_id", "normalized_artist_name"),
        Index("idx_spotify_vinyl_release_matches_artist", "normalized_artist_name"),
        Index("idx_spotify_vinyl_release_matches_user_confidence", "user_id", "confidence_score"),
        Index("idx_spotify_vinyl_release_matches_confidence", "confidence_score"),
    )

    match_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    release_id: Mapped[str] = mapped_column(String, ForeignKey("releases.id", ondelete="CASCADE"), nullable=False)
    normalized_artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_album_name: Mapped[str] = mapped_column(String(512), nullable=False)
    spotify_artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    spotify_album_name: Mapped[str] = mapped_column(String(512), nullable=False)
    release_artist: Mapped[str] = mapped_column(String(512), nullable=False)
    release_title: Mapped[str] = mapped_column(String(512), nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    match_type: Mapped[str] = mapped_column(String(40), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
