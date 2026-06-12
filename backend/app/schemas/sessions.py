from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: str
    session_group_id: str | None = None
    side: str | None = None
    track_positions: list[str] | None = None
    rating: int | None = None
    mood: str | None = None
    notes: str | None = None
    played_at: str


class UpdateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    side: str | None = None
    track_positions: list[str] | None = None
    rating: int | None = None
    mood: str | None = None
    notes: str | None = None


class SessionCreateResponse(BaseModel):
    session_id: str
    timestamp: datetime
    session_group_id: str | None = None
    status: str


class StartSessionGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=100)
    started_at: str | None = None
    style_focus: str | None = None
    mood_direction: str | None = None
    session_type: str | None = None


class FinishSessionGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ended_at: str | None = None
    style_focus: str | None = None
    mood_direction: str | None = None
    session_type: str | None = None
    notes: str | None = Field(default=None, max_length=1000)


class UpdateSessionGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_focus: str | None = None
    mood_direction: str | None = None
    session_type: str | None = None
    notes: str | None = Field(default=None, max_length=1000)


class SessionGroupResponse(BaseModel):
    id: str
    title: str | None = None
    status: str
    style_focus: str
    mood_direction: str
    session_type: str
    notes: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    editable_until: datetime | None = None


class ActiveSessionGroupResponse(BaseModel):
    session_group: SessionGroupResponse | None = None


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


class SessionTrackResponse(BaseModel):
    position: str
    title: str
    duration: str | None = None
    sequence: int | None = None


class SessionResponse(BaseModel):
    id: str
    release_id: str
    session_group_id: str | None = None
    rating: int | None
    mood: str | None
    notes: str | None
    played_at: datetime | None
    vinyl_side: str | None
    tracks: list[SessionTrackResponse] = Field(default_factory=list)
    created_at: datetime
    can_edit: bool
    editable_until: datetime


class ReleaseSessionHistoryItem(BaseModel):
    session_id: str
    session_group_id: str | None = None
    date: str | None
    played_at: datetime | None = None
    side: str | None
    tracks: list[SessionTrackResponse] = Field(default_factory=list)
    rating: int | None
    mood: str | None
    notes: str | None = None
    has_notes: bool
    created_at: datetime
    can_edit: bool
    editable_until: datetime


class ReleaseSessionsResponse(BaseModel):
    sessions: list[ReleaseSessionHistoryItem]


class HomeRecentSessionGroupItem(BaseModel):
    id: str
    title: str | None = None
    status: str
    style_focus: str
    mood_direction: str
    session_type: str
    notes: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    can_edit: bool
    editable_until: datetime | None = None


class HomeRecentSessionItem(BaseModel):
    session_id: str
    release_id: str
    session_group_id: str | None = None
    session_group: HomeRecentSessionGroupItem | None = None
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
    created_at: datetime
    can_edit: bool
    editable_until: datetime


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
