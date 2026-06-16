from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReleaseImportRequest(BaseModel):
    discogs_release_id: int = Field(gt=0)
    force_refresh: bool = False


class ClientDiscogsReleaseImportRequest(BaseModel):
    discogs_release: dict[str, Any]


class ReleaseSideOptionResponse(BaseModel):
    value: str
    label: str
    side: str
    disc_number: int | None = None


class ReleaseTrackCreditResponse(BaseModel):
    name: str
    role: str | None = None


class ReleaseTrackResponse(BaseModel):
    position: str
    title: str
    duration: str | None = None
    extra_artists: list[ReleaseTrackCreditResponse] = Field(default_factory=list)


class ReleaseArtistResponse(BaseModel):
    name: str
    discogs_artist_id: int


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
    is_favorite: bool = False
    has_full_discogs_info: bool = False
    available_sides: list[str] = Field(default_factory=list)
    available_side_options: list[ReleaseSideOptionResponse] = Field(default_factory=list)
    tracklist: list[ReleaseTrackResponse] = Field(default_factory=list)
    discogs_artists: list[ReleaseArtistResponse] = Field(default_factory=list)
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


class RecordFlowReleaseSummaryResponse(BaseModel):
    release_id: str
    artist: str
    title: str
    year: int | None = None
    thumbnail_url: str | None = None
    cover_image_url: str | None = None
    styles: list[str] | None = None
    count: int


class RecordFlowMoodTransitionResponse(BaseModel):
    previous_mood: str | None = None
    current_mood: str | None = None
    next_mood: str | None = None
    count: int


class RecordFlowInsightsResponse(BaseModel):
    release_id: str
    before: list[RecordFlowReleaseSummaryResponse] = Field(default_factory=list)
    after: list[RecordFlowReleaseSummaryResponse] = Field(default_factory=list)
    mood_transitions: list[RecordFlowMoodTransitionResponse] = Field(default_factory=list)
    sample_size: int
    confidence: str


class ReleaseImportResponse(BaseModel):
    release_id: str
    discogs_release_id: int
    status: str


class ReleaseFavoriteRequest(BaseModel):
    is_favorite: bool
