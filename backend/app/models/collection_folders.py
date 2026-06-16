from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CollectionFolder(Base):
    """Discogs collection folder metadata imported during collection sync."""

    __tablename__ = "collection_folders"
    __table_args__ = (
        Index("idx_collection_folders_discogs_folder_id", "discogs_folder_id"),
        Index("idx_collection_folders_is_default", "is_default"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discogs_folder_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    item_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    last_discogs_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReleaseCollectionFolder(Base):
    """Join table linking imported releases to Discogs collection folders."""

    __tablename__ = "release_collection_folders"
    __table_args__ = (
        UniqueConstraint("release_id", "collection_folder_id", name="uq_release_collection_folder"),
        Index("idx_release_collection_folders_release_id", "release_id"),
        Index("idx_release_collection_folders_folder_id", "collection_folder_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_id: Mapped[str] = mapped_column(String, ForeignKey("releases.id", ondelete="CASCADE"), nullable=False)
    collection_folder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("collection_folders.id", ondelete="CASCADE"), nullable=False
    )
    discogs_instance_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    date_added: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_discogs_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
