from types import SimpleNamespace

import pytest

from app.services.analytics_service import AnalyticsService, AnalyticsValidationError


class StubAnalyticsRepository:
    def __init__(self) -> None:
        self.top_limit: int | None = None

    def get_monthly_play_counts(self, _db):
        return [("2026-01", 2), ("2026-02", 3)]

    def get_top_records(self, _db, *, limit: int):
        self.top_limit = limit
        release = SimpleNamespace(
            id="release-123",
            discogs_release_id=555123,
            artist="Boards of Canada",
            title="Music Has The Right To Children",
        )
        return [(release, 4, 4.25)]

    def get_rating_distribution(self, _db):
        return [(2, 1), (5, 3)]

    def get_mood_distribution(self, _db):
        return [("Calm", 3), ("", 2), (None, 1)]


def test_get_monthly_plays_maps_repository_rows() -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    result = service.get_monthly_plays(db=object())

    assert [(item.month, item.plays) for item in result] == [("2026-01", 2), ("2026-02", 3)]


def test_get_top_records_validates_limit_and_maps_rows() -> None:
    repository = StubAnalyticsRepository()
    service = AnalyticsService(analytics_repository=repository)

    result = service.get_top_records(db=object(), limit=7)

    assert repository.top_limit == 7
    assert result[0].release.id == "release-123"
    assert result[0].plays == 4
    assert result[0].average_rating == 4.25


@pytest.mark.parametrize("limit", [0, 51])
def test_get_top_records_rejects_invalid_limit(limit: int) -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    with pytest.raises(AnalyticsValidationError) as exc_info:
        service.get_top_records(db=object(), limit=limit)

    assert exc_info.value.code == "invalid_limit"


def test_get_rating_distribution_fills_missing_ratings() -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    result = service.get_rating_distribution(db=object())

    assert result == {"1": 0, "2": 1, "3": 0, "4": 0, "5": 3}


def test_get_mood_distribution_skips_blank_moods() -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    result = service.get_mood_distribution(db=object())

    assert result == {"Calm": 3}
