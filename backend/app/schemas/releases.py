from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReleaseImportRequest(BaseModel):
    discogs_release_id: int = Field(gt=0)
    force_refresh: bool = False


class ReleaseSideOptionResponse(BaseModel):
    value: str
    label: str
    side: str
    disc_number: int | None = None


class ReleaseTrackResponse(BaseModel):
    position: str
    title: str
    duration: str | None = None


class ReleaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    discogs_release_id: int
    artist: str
    title: str
    year: int | None
    format: str | None = None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    genres: list[str] | None
    styles: list[str] | None
    thumbnail_url: str | None = None
    cover_image_url: str | None
    in_collection: bool = False
    collection_added_at: datetime | None = None
    collection_removed_at: datetime | None = None
    last_discogs_sync_at: datetime | None = None
    discogs_instance_id: int | None = None
    has_full_discogs_info: bool = False
    available_sides: list[str] = Field(default_factory=list)
    available_side_options: list[ReleaseSideOptionResponse] = Field(default_factory=list)
    tracklist: list[ReleaseTrackResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ReleaseSearchResult(BaseModel):
    release_id: str | None = None
    discogs_release_id: int
    artist: str
    title: str
    year: int | None = None
    label: str | None = None
    catalog_number: str | None = None
    thumbnail_url: str | None = None
    format: str | None = None


class ReleaseSearchResponse(BaseModel):
    results: list[ReleaseSearchResult]
    limit: int
    offset: int
    has_more: bool | None = None


class ReleaseImportResponse(BaseModel):
    release_id: str
    discogs_release_id: int
    status: str
