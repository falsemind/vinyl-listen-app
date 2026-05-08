from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DiscogsReleaseCache(Base):
    """SQLAlchemy model for caching Discogs release metadata.

    This table stores the raw JSON payload returned by the Discogs API so that we can
    avoid repeated API calls and stay within rate limits.  The primary key is the
    Discogs release ID, which uniquely identifies each record on Discogs.
    """

    __tablename__ = "discogs_release_cache"
    __table_args__ = (Index("idx_discogs_release_cache_last_accessed_at", "last_accessed_at"),)

    # Primary key – Discogs release identifier.
    discogs_release_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    # Full raw JSON payload from Discogs.
    raw_discogs_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Timestamp when the record was cached.
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Timestamp when the cache entry was last accessed.
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
