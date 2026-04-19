from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReleaseImportRequest(BaseModel):
    discogs_release_id: int = Field(gt=0)
    force_refresh: bool = False


class ReleaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    discogs_release_id: int
    artist: str
    title: str
    year: int | None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    genres: list[str] | None
    styles: list[str] | None
    cover_image_url: str | None
    created_at: datetime
    updated_at: datetime


class ReleaseImportResponse(BaseModel):
    release_id: str
    discogs_release_id: int
    status: str
