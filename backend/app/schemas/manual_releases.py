from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.manual_release_policy import (
    CATALOG_NUMBER_LIMIT,
    LABEL_NAME_LIMIT,
    MAX_MANUAL_RELEASE_ARTISTS,
    MAX_MANUAL_RELEASE_COVER_BYTES,
    MAX_MANUAL_RELEASE_DRAFTS,
    MAX_MANUAL_RELEASE_TRACKS,
    MAX_RELEASE_YEAR,
    MIN_RELEASE_YEAR,
    TITLE_LIMIT,
    TRACK_CREDIT_NAME_LIMIT,
    TRACK_DURATION_LIMIT,
    TRACK_POSITION_LIMIT,
    TRACK_TITLE_LIMIT,
)


class ManualReleaseFormat(StrEnum):
    VINYL = "Vinyl"
    CD = "CD"
    TAPE = "Tape"
    OTHER = "Other"


class ManualReleaseVinylSize(StrEnum):
    SEVEN_INCH = "7"
    TEN_INCH = "10"
    TWELVE_INCH = "12"
    OTHER = "Other"


class ManualReleaseVinylSpeed(StrEnum):
    THIRTY_THREE = "33 1/3"
    FORTY_FIVE = "45"
    SEVENTY_EIGHT = "78"
    OTHER = "Other"


class ManualReleaseTrackCreditRole(StrEnum):
    FEATURING = "Featuring"
    REMIX = "Remix"
    PRODUCER = "Producer"
    WRITTEN_BY = "Written-By"
    OTHER = "Other"


class ManualReleaseBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def trim_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            normalized_items: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    trimmed_item = item.strip()
                    if trimmed_item:
                        normalized_items.append(trimmed_item)
                else:
                    normalized_items.append(item)
            return normalized_items
        return value


class ManualReleaseTrackCreditInput(ManualReleaseBaseModel):
    role: ManualReleaseTrackCreditRole
    name: str | None = Field(default=None, max_length=TRACK_CREDIT_NAME_LIMIT.max_length)


class ManualReleaseTrackInput(ManualReleaseBaseModel):
    title: str | None = Field(default=None, max_length=TRACK_TITLE_LIMIT.max_length)
    position: str | None = Field(default=None, max_length=TRACK_POSITION_LIMIT.max_length)
    duration: str | None = Field(default=None, max_length=TRACK_DURATION_LIMIT.max_length)
    credits: list[ManualReleaseTrackCreditInput] = Field(default_factory=list)


class ManualReleaseFormData(ManualReleaseBaseModel):
    artists: list[str] = Field(default_factory=list, max_length=MAX_MANUAL_RELEASE_ARTISTS)
    title: str | None = Field(default=None, max_length=TITLE_LIMIT.max_length)
    year: int | None = Field(default=None, ge=MIN_RELEASE_YEAR, le=MAX_RELEASE_YEAR)
    label: str | None = Field(default=None, max_length=LABEL_NAME_LIMIT.max_length)
    catalog_number: str | None = Field(default=None, max_length=CATALOG_NUMBER_LIMIT.max_length)
    barcode: str | None = Field(default=None, max_length=32)
    format: ManualReleaseFormat | None = None
    vinyl_size: ManualReleaseVinylSize | None = None
    vinyl_speed: ManualReleaseVinylSpeed | None = None
    vinyl_disc_count: int | None = Field(default=None, ge=1, le=6)
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    tracklist: list[ManualReleaseTrackInput] = Field(default_factory=list, max_length=MAX_MANUAL_RELEASE_TRACKS)


class ManualReleaseDraftPayload(ManualReleaseBaseModel):
    form_data: ManualReleaseFormData
    completion_state: dict[str, Any] | None = None


class ManualReleaseSaveRequest(ManualReleaseBaseModel):
    form_data: ManualReleaseFormData | None = None
    draft_id: str | None = None


class ManualReleaseUpdateRequest(ManualReleaseBaseModel):
    form_data: ManualReleaseFormData


class ManualReleaseDraftSummaryResponse(BaseModel):
    id: str
    artist: str | None
    title: str | None
    year: int | None
    label: str | None
    catalog_number: str | None
    format: str | None
    cover_thumbnail_url: str | None
    completion_state: dict[str, Any] | None
    updated_at: datetime


class ManualReleaseDraftResponse(ManualReleaseDraftSummaryResponse):
    form_data: ManualReleaseFormData
    cover_image_url: str | None
    cover_content_type: str | None
    cover_size_bytes: int | None
    created_at: datetime


class ManualReleaseDraftListResponse(BaseModel):
    items: list[ManualReleaseDraftSummaryResponse]
    limit: int = MAX_MANUAL_RELEASE_DRAFTS
    remaining_slots: int


class ManualReleaseSaveResponse(BaseModel):
    id: str
    title: str
    artist: str
    in_collection: bool


class ManualReleaseDetailResponse(BaseModel):
    id: str
    title: str
    artist: str
    in_collection: bool
    form_data: ManualReleaseFormData
    cover_image_url: str | None
    cover_thumbnail_url: str | None
    cover_content_type: str | None
    cover_size_bytes: int | None
    created_at: datetime
    updated_at: datetime


class ManualReleaseCoverUploadResponse(BaseModel):
    content_type: str
    size_bytes: int = Field(le=MAX_MANUAL_RELEASE_COVER_BYTES)
