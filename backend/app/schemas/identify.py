from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    format: str | None = None
    match_source: str
    matched_on: list[str]
    confidence: float


class IdentifyResponse(BaseModel):
    candidates: list[IdentifyCandidateResponse]


class IdentifyJobStatus(StrEnum):
    QUEUED = "queued"
    UPLOAD_RECEIVED = "upload_received"
    TEXT_RECEIVED = "text_received"
    PREPROCESSING_IMAGE = "preprocessing_image"
    EXTRACTING_TEXT = "extracting_text"
    PARSING_IDENTIFIERS = "parsing_identifiers"
    SEARCHING_LOCAL = "searching_local"
    SEARCHING_DISCOGS = "searching_discogs"
    RANKING_CANDIDATES = "ranking_candidates"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELED = "canceled"


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
    cancel_requested: bool = False
    result: IdentifyResponse | None = None
    error: IdentifyJobError | None = None


class IdentifyTextSourceType(StrEnum):
    ANDROID_MLKIT_TEXT = "ANDROID_MLKIT_TEXT"


class IdentifyTextJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[str] = Field(min_length=1, max_length=200)
    selected_catalog_number: str | None = Field(default=None, max_length=100)
    selected_barcode: str | None = Field(default=None, max_length=32)
    source_type: IdentifyTextSourceType = IdentifyTextSourceType.ANDROID_MLKIT_TEXT

    @field_validator("lines")
    @classmethod
    def normalize_lines(cls, value: list[str]) -> list[str]:
        lines = [line.strip() for line in value if line.strip()]
        if not lines:
            raise ValueError("At least one non-empty OCR text line is required.")
        return lines

    @field_validator("selected_catalog_number", "selected_barcode")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
