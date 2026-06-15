from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CollectionSettings(Base):
    """Persistent app-level collection settings."""

    __tablename__ = "collection_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    source_of_truth: Mapped[str] = mapped_column(String(20), nullable=False, default="APP", server_default="APP")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
