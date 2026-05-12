from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class IdentifyCandidateResponse(BaseModel):
    discogs_release_id: int
    release_id: str | None
    artist: str
    title: str
    year: int | None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    cover_image_url: str | None
    match_source: str
    matched_on: list[str]
    confidence: float


class IdentifyResponse(BaseModel):
    candidates: list[IdentifyCandidateResponse]


class IdentifyJobStatus(StrEnum):
    QUEUED = "queued"
    UPLOAD_RECEIVED = "upload_received"
    PREPROCESSING_IMAGE = "preprocessing_image"
    EXTRACTING_TEXT = "extracting_text"
    PARSING_IDENTIFIERS = "parsing_identifiers"
    SEARCHING_LOCAL = "searching_local"
    SEARCHING_DISCOGS = "searching_discogs"
    RANKING_CANDIDATES = "ranking_candidates"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class IdentifyJobError(BaseModel):
    code: str
    message: str
    failed_step: str


class IdentifyJobStatusResponse(BaseModel):
    job_id: str
    status: IdentifyJobStatus
    message: str
    created_at: datetime
    updated_at: datetime
    result: IdentifyResponse | None = None
    error: IdentifyJobError | None = None
