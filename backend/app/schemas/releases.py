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
    available_sides: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ReleaseSearchResult(BaseModel):
    discogs_release_id: int
    artist: str
    title: str
    year: int | None = None
    label: str | None = None
    catalog_number: str | None = None
    thumbnail_url: str | None = None


class ReleaseSearchResponse(BaseModel):
    results: list[ReleaseSearchResult]
    limit: int
    offset: int


class ReleaseImportResponse(BaseModel):
    release_id: str
    discogs_release_id: int
    status: str
