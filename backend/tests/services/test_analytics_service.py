from types import SimpleNamespace

import pytest

from app.services.analytics_service import AnalyticsService, AnalyticsValidationError


class StubAnalyticsRepository:
    def __init__(self) -> None:
        self.top_limit: int | None = None
        self.month_calls: list[tuple[str, int, int]] = []
        self.rating_calls: list[tuple[int, int, int]] = []
        self.mood_calls: list[tuple[str, int, int]] = []
        self.style_calls: list[tuple[str, int, int]] = []
        self.style_page_calls: list[tuple[str, int, int]] = []
        self.style_count_calls: list[str] = []
        self.release = SimpleNamespace(
            id="release-123",
            discogs_release_id=555123,
            artist="Boards of Canada",
            title="Music Has The Right To Children",
            cover_image_url="https://img.discogs.com/cover.jpg",
        )
        self.session = SimpleNamespace(
            id="session-123",
            release_id="release-123",
            played_at=None,
            vinyl_side="A",
            rating=5,
            mood="Focused",
            notes="",
        )

    def get_monthly_play_counts(self, _db):
        return [("2026-01", 2), ("2026-02", 3)]

    def get_top_records(self, _db, *, limit: int):
        self.top_limit = limit
        return [(self.release, 4, 4.25, "Roygbiv", "Focused")]

    def get_sessions_for_month(self, _db, *, month: str, limit: int, offset: int):
        self.month_calls.append((month, limit, offset))
        return [(self.session, self.release)]

    def count_sessions_for_month(self, _db, *, month: str):
        return 12 if month == "2026-05" else 0

    def get_records_for_rating(self, _db, *, rating: int, limit: int, offset: int):
        self.rating_calls.append((rating, limit, offset))
        return [(self.release, 3)]

    def count_records_for_rating(self, _db, *, rating: int):
        return 8 if rating == 5 else 0

    def get_records_for_mood(self, _db, *, mood: str, limit: int, offset: int):
        self.mood_calls.append((mood, limit, offset))
        return [(self.release, 2)]

    def count_records_for_mood(self, _db, *, mood: str):
        return 6 if mood == "Focused" else 0

    def get_records_for_style(self, _db, *, style: str, limit: int, offset: int):
        self.style_calls.append((style, limit, offset))
        return [(self.release, 4)]

    def get_records_for_style_page(self, _db, *, style: str, limit: int, offset: int):
        self.style_page_calls.append((style, limit, offset))
        return ([(self.release, 4)], 9 if style == "Dub Techno" else 0)

    def count_records_for_style(self, _db, *, style: str):
        self.style_count_calls.append(style)
        return 9 if style == "Dub Techno" else 0

    def get_rating_distribution(self, _db):
        return [(2, 1), (5, 3)]

    def get_mood_distribution(self, _db):
        return [("Calm", 3), ("", 2), (None, 1)]

    def get_style_distribution(self, _db):
        return [("Dub Techno", 4), ("", 2), (None, 1)]


class EmptyAnalyticsRepository(StubAnalyticsRepository):
    def get_sessions_for_month(self, _db, *, month: str, limit: int, offset: int):
        self.month_calls.append((month, limit, offset))
        return []

    def count_sessions_for_month(self, _db, *, month: str):
        _ = month
        return 0

    def get_records_for_rating(self, _db, *, rating: int, limit: int, offset: int):
        self.rating_calls.append((rating, limit, offset))
        return []

    def count_records_for_rating(self, _db, *, rating: int):
        _ = rating
        return 0


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
    assert result[0].top_track == "Roygbiv"
    assert result[0].top_mood == "Focused"


@pytest.mark.parametrize("limit", [0, 251])
def test_get_top_records_rejects_invalid_limit(limit: int) -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    with pytest.raises(AnalyticsValidationError) as exc_info:
        service.get_top_records(db=object(), limit=limit)

    assert exc_info.value.code == "invalid_limit"


def test_get_sessions_for_month_validates_and_maps_page() -> None:
    repository = StubAnalyticsRepository()
    service = AnalyticsService(analytics_repository=repository)

    result = service.get_sessions_for_month(db=object(), month="2026-05", limit=5, offset=5)

    assert repository.month_calls == [("2026-05", 5, 5)]
    assert result.sessions[0].session.id == "session-123"
    assert result.sessions[0].release.id == "release-123"
    assert result.pagination.limit == 5
    assert result.pagination.offset == 5
    assert result.pagination.total == 12
    assert result.pagination.has_more is True


@pytest.mark.parametrize("month", ["2026-5", "2026-13", "bad"])
def test_get_sessions_for_month_rejects_invalid_month(month: str) -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    with pytest.raises(AnalyticsValidationError) as exc_info:
        service.get_sessions_for_month(db=object(), month=month)

    assert exc_info.value.code == "invalid_month"


@pytest.mark.parametrize(
    ("limit", "offset", "expected_code"),
    [
        (0, 0, "invalid_limit"),
        (251, 0, "invalid_limit"),
        (10, -1, "invalid_offset"),
    ],
)
def test_get_sessions_for_month_rejects_invalid_pagination(limit: int, offset: int, expected_code: str) -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    with pytest.raises(AnalyticsValidationError) as exc_info:
        service.get_sessions_for_month(db=object(), month="2026-05", limit=limit, offset=offset)

    assert exc_info.value.code == expected_code


def test_get_records_for_rating_validates_and_maps_page() -> None:
    repository = StubAnalyticsRepository()
    service = AnalyticsService(analytics_repository=repository)

    result = service.get_records_for_rating(db=object(), rating=5, limit=4, offset=2)

    assert repository.rating_calls == [(5, 4, 2)]
    assert result.records[0].release.id == "release-123"
    assert result.records[0].count == 3
    assert result.pagination.total == 8
    assert result.pagination.has_more is True


def test_drilldown_pages_return_empty_results_without_more_pages() -> None:
    repository = EmptyAnalyticsRepository()
    service = AnalyticsService(analytics_repository=repository)

    sessions_result = service.get_sessions_for_month(db=object(), month="2026-05", limit=10, offset=0)
    records_result = service.get_records_for_rating(db=object(), rating=5, limit=10, offset=0)

    assert sessions_result.sessions == []
    assert sessions_result.pagination.total == 0
    assert sessions_result.pagination.has_more is False
    assert records_result.records == []
    assert records_result.pagination.total == 0
    assert records_result.pagination.has_more is False


def test_get_records_for_rating_rejects_invalid_rating() -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    with pytest.raises(AnalyticsValidationError) as exc_info:
        service.get_records_for_rating(db=object(), rating=6)

    assert exc_info.value.code == "invalid_rating"


def test_get_records_for_mood_normalizes_label() -> None:
    repository = StubAnalyticsRepository()
    service = AnalyticsService(analytics_repository=repository)

    result = service.get_records_for_mood(db=object(), mood=" Focused ", limit=5, offset=0)

    assert repository.mood_calls == [("Focused", 5, 0)]
    assert result.records[0].count == 2
    assert result.pagination.total == 6


def test_get_records_for_style_normalizes_label() -> None:
    repository = StubAnalyticsRepository()
    service = AnalyticsService(analytics_repository=repository)

    result = service.get_records_for_style(db=object(), style=" Dub Techno ", limit=5, offset=0)

    assert repository.style_page_calls == [("Dub Techno", 5, 0)]
    assert repository.style_count_calls == []
    assert result.records[0].count == 4
    assert result.pagination.total == 9


@pytest.mark.parametrize(
    ("method_name", "kwargs", "expected_code"),
    [
        ("get_records_for_mood", {"mood": ""}, "invalid_mood"),
        ("get_records_for_style", {"style": "  "}, "invalid_style"),
    ],
)
def test_record_label_drilldowns_reject_blank_labels(
    method_name: str,
    kwargs: dict[str, str],
    expected_code: str,
) -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())
    method = getattr(service, method_name)

    with pytest.raises(AnalyticsValidationError) as exc_info:
        method(db=object(), **kwargs)

    assert exc_info.value.code == expected_code


def test_get_rating_distribution_fills_missing_ratings() -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    result = service.get_rating_distribution(db=object())

    assert result == {"1": 0, "2": 1, "3": 0, "4": 0, "5": 3}


def test_get_mood_distribution_skips_blank_moods() -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    result = service.get_mood_distribution(db=object())

    assert result == {"Calm": 3}


def test_get_style_distribution_skips_blank_styles() -> None:
    service = AnalyticsService(analytics_repository=StubAnalyticsRepository())

    result = service.get_style_distribution(db=object())

    assert result == {"Dub Techno": 4}
