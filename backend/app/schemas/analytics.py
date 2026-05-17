from pydantic import BaseModel


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


class AnalyticsTopRecordsResponse(BaseModel):
    records: list[AnalyticsTopRecordItem]


class RatingDistributionResponse(BaseModel):
    ratings: dict[str, int]


class MoodDistributionResponse(BaseModel):
    moods: dict[str, int]
