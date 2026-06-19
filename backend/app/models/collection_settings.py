from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CollectionSettings(Base):
    """Persistent collection settings owned by one account or legacy shared mode."""

    __tablename__ = "collection_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_collection_settings_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_of_truth: Mapped[str] = mapped_column(String(20), nullable=False, default="APP", server_default="APP")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
