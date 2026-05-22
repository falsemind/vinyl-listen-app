from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: str
    side: str | None = None
    rating: int | None = None
    mood: str | None = None
    notes: str | None = None
    played_at: str


class SessionCreateResponse(BaseModel):
    session_id: str
    timestamp: datetime
    status: str


class SessionMoodItem(BaseModel):
    name: str
    is_custom: bool


class SessionMoodsResponse(BaseModel):
    moods: list[SessionMoodItem]


class CreateSessionMoodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class SessionMoodResponse(BaseModel):
    mood: SessionMoodItem


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    release_id: str
    rating: int | None
    mood: str | None
    notes: str | None
    played_at: datetime | None
    vinyl_side: str | None
    created_at: datetime


class ReleaseSessionHistoryItem(BaseModel):
    session_id: str
    date: str | None
    played_at: datetime | None = None
    side: str | None
    rating: int | None
    mood: str | None
    notes: str | None = None
    has_notes: bool


class ReleaseSessionsResponse(BaseModel):
    sessions: list[ReleaseSessionHistoryItem]


class HomeRecentSessionItem(BaseModel):
    session_id: str
    release_id: str
    artist: str
    title: str
    thumbnail_url: str | None = None
    date: str | None
    played_at: datetime | None = None
    side: str | None
    rating: int | None
    mood: str | None
    has_notes: bool


class HomeTopRecordItem(BaseModel):
    release_id: str
    artist: str
    title: str
    thumbnail_url: str | None = None
    plays: int
    average_rating: float | None


class HomeSummaryResponse(BaseModel):
    recent_sessions: list[HomeRecentSessionItem]
    total_sessions: int
    records_this_month: int
    top_records: list[HomeTopRecordItem]
