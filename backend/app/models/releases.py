from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Releases(Base):
    """SQLAlchemy model for the releases table.

    The columns map directly to the database schema described in
    ``docs/architecture/database-schema.md``.  The implementation follows the
    same style as :class:`Sessions` – ``id`` is a UUID stored as a string, and
    timestamps use :func:`sqlalchemy.func.now`.
    """

    __tablename__ = "releases"
    __table_args__ = (
        Index("idx_releases_artist", "artist"),
        Index("idx_releases_title", "title"),
        Index("idx_releases_genres", "genres", postgresql_using="gin"),
        Index("idx_releases_styles", "styles", postgresql_using="gin"),
        Index("idx_releases_in_collection", "in_collection"),
        Index("idx_releases_collection_added_at", "collection_added_at"),
        Index("idx_releases_is_favorite", "is_favorite"),
    )

    # Primary key – a UUID stored as a string for portability.
    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Discogs identifier – unique.
    discogs_release_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)

    # Core metadata.
    artist: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format: Mapped[str | None] = mapped_column(String, nullable=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    catalog_number: Mapped[str | None] = mapped_column(String, nullable=True)
    barcode: Mapped[str | None] = mapped_column(String, nullable=True)

    # Array columns for genres and styles – PostgreSQL array of text.
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    styles: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Discogs collection membership. Historical session data remains linked when
    # a release is no longer present in the user's Discogs collection.
    in_collection: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    collection_added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collection_removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_discogs_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discogs_instance_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # Timestamps.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ManualRelease(Base):
    """User-owned committed manual release metadata."""

    __tablename__ = "manual_releases"
    __table_args__ = (
        Index("idx_manual_releases_user_updated", "user_id", "updated_at"),
        Index("idx_manual_releases_user_title", "user_id", "title"),
        Index("idx_manual_releases_in_collection", "in_collection"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artist: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    catalog_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(14), nullable=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    styles: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    artists: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    labels: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    identifiers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    format_details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tracklist: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    cover_storage_key: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cover_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    in_collection: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    collection_added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collection_removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ManualReleaseDraft(Base):
    """Partial manual release form state saved before collection creation."""

    __tablename__ = "manual_release_drafts"
    __table_args__ = (Index("idx_manual_release_drafts_user_updated", "user_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    form_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    completion_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cover_storage_key: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cover_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
