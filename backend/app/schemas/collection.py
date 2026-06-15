from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class CollectionSourceOfTruth(StrEnum):
    APP = "APP"
    DISCOGS = "DISCOGS"


class CollectionSettingsRequest(BaseModel):
    source_of_truth: CollectionSourceOfTruth


class CollectionSettingsResponse(BaseModel):
    source_of_truth: CollectionSourceOfTruth


class CollectionSyncJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


class CollectionSyncJobStep(StrEnum):
    FETCHING = "fetching"
    IMPORTING = "importing"
    LOADING = "loading"
    FINALIZING = "finalizing"


class CollectionSyncJobError(BaseModel):
    code: str
    message: str
    failed_step: str


class CollectionSyncJobStatusResponse(BaseModel):
    job_id: str
    status: CollectionSyncJobStatus
    step: CollectionSyncJobStep | None = None
    message: str
    total_items: int = 0
    processed_items: int = 0
    added_count: int = 0
    updated_count: int = 0
    removed_count: int = 0
    error: CollectionSyncJobError | None = None
    created_at: datetime
    updated_at: datetime


class CollectionReleaseResponse(BaseModel):
    id: str
    discogs_release_id: int
    title: str
    artist: str
    year: int | None = None
    format: str | None = None
    label: str | None = None
    catalog_number: str | None = None
    styles: list[str] | None = None
    thumb_url: str | None = None
    collection_added_at: datetime | None = None
    in_collection: bool
    is_favorite: bool = False


class CollectionReleasesResponse(BaseModel):
    items: list[CollectionReleaseResponse]
    limit: int
    offset: int
    total: int
    has_more: bool
    has_favorites: bool = False
