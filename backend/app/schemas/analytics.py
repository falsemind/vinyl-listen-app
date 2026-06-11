from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.sessions import SessionTrackResponse


class MonthlyPlayItem(BaseModel):
    month: str
    plays: int


class MonthlyPlaysResponse(BaseModel):
    data: list[MonthlyPlayItem]


class AnalyticsTopRecordItem(BaseModel):
    release_id: str
    discogs_release_id: int
    artist: str
    title: str
    thumbnail_url: str | None = None
    plays: int
    average_rating: float | None
    top_track: str | None = None
    top_mood: str | None = None


class AnalyticsTopRecordsResponse(BaseModel):
    records: list[AnalyticsTopRecordItem]


class AnalyticsPagination(BaseModel):
    limit: int
    offset: int
    total: int
    has_more: bool


class AnalyticsSessionItem(BaseModel):
    session_id: str
    release_id: str
    session_group_id: str | None = None
    artist: str
    title: str
    thumbnail_url: str | None = None
    date: str | None
    played_at: datetime | None = None
    side: str | None
    tracks: list[SessionTrackResponse] = Field(default_factory=list)
    rating: int | None
    mood: str | None
    has_notes: bool


class AnalyticsSessionsResponse(BaseModel):
    sessions: list[AnalyticsSessionItem]
    pagination: AnalyticsPagination


class AnalyticsRecordCountItem(BaseModel):
    release_id: str
    discogs_release_id: int
    artist: str
    title: str
    thumbnail_url: str | None = None
    count: int


class AnalyticsRecordCountsResponse(BaseModel):
    records: list[AnalyticsRecordCountItem]
    pagination: AnalyticsPagination


class RatingDistributionResponse(BaseModel):
    ratings: dict[str, int]


class MoodDistributionResponse(BaseModel):
    moods: dict[str, int]


class StyleDistributionResponse(BaseModel):
    styles: dict[str, int]
