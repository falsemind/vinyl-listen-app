from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes.analytics import get_analytics_service
from app.main import app
from app.services.analytics_service import (
    AnalyticsPagination,
    AnalyticsRecordCount,
    AnalyticsRecordCountPage,
    AnalyticsSession,
    AnalyticsSessionPage,
    AnalyticsTopRecord,
    AnalyticsValidationError,
    MonthlyPlayCount,
)


class StubAnalyticsService:
    def __init__(self) -> None:
        self.top_calls: list[int] = []
        self.top_error: Exception | None = None
        self.month_calls: list[tuple[str, int, int]] = []
        self.rating_calls: list[tuple[int, int, int]] = []
        self.mood_calls: list[tuple[str, int, int]] = []
        self.style_calls: list[tuple[str, int, int]] = []
        self.drilldown_error: Exception | None = None
        self.empty_drilldowns = False
        self.release = SimpleNamespace(
            id="release-123",
            discogs_release_id=555123,
            artist="Boards of Canada",
            title="Music Has The Right To Children",
            cover_image_url="https://img.discogs.com/cover.jpg",
        )
        self.session = SimpleNamespace(
            id="session-123",
            played_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
            vinyl_side="A",
            rating=5,
            mood="Focused",
            notes="Great listen",
        )

    def get_monthly_plays(self, _db):
        return [
            MonthlyPlayCount(month="2026-01", plays=2),
            MonthlyPlayCount(month="2026-02", plays=3),
        ]

    def get_top_records(self, _db, *, limit: int):
        self.top_calls.append(limit)
        if self.top_error is not None:
            raise self.top_error
        return [
            AnalyticsTopRecord(
                release=self.release,
                plays=5,
                average_rating=4.46,
            )
        ]

    def get_sessions_for_month(self, _db, *, month: str, limit: int, offset: int):
        self.month_calls.append((month, limit, offset))
        if self.drilldown_error is not None:
            raise self.drilldown_error
        if self.empty_drilldowns:
            return AnalyticsSessionPage(
                sessions=[],
                pagination=AnalyticsPagination(limit=limit, offset=offset, total=0, has_more=False),
            )
        return AnalyticsSessionPage(
            sessions=[AnalyticsSession(session=self.session, release=self.release)],
            pagination=AnalyticsPagination(limit=limit, offset=offset, total=12, has_more=True),
        )

    def get_records_for_rating(self, _db, *, rating: int, limit: int, offset: int):
        self.rating_calls.append((rating, limit, offset))
        if self.drilldown_error is not None:
            raise self.drilldown_error
        return self._record_count_page(limit=limit, offset=offset)

    def get_records_for_mood(self, _db, *, mood: str, limit: int, offset: int):
        self.mood_calls.append((mood, limit, offset))
        if self.drilldown_error is not None:
            raise self.drilldown_error
        return self._record_count_page(limit=limit, offset=offset)

    def get_records_for_style(self, _db, *, style: str, limit: int, offset: int):
        self.style_calls.append((style, limit, offset))
        if self.drilldown_error is not None:
            raise self.drilldown_error
        return self._record_count_page(limit=limit, offset=offset)

    def get_rating_distribution(self, _db):
        return {"1": 0, "2": 1, "3": 0, "4": 2, "5": 3}

    def get_mood_distribution(self, _db):
        return {"Calm": 3, "Focused": 2}

    def get_style_distribution(self, _db):
        return {"Dub Techno": 4, "House": 2}

    def _record_count_page(self, *, limit: int, offset: int) -> AnalyticsRecordCountPage:
        if self.empty_drilldowns:
            return AnalyticsRecordCountPage(
                records=[],
                pagination=AnalyticsPagination(limit=limit, offset=offset, total=0, has_more=False),
            )
        return AnalyticsRecordCountPage(
            records=[AnalyticsRecordCount(release=self.release, count=7)],
            pagination=AnalyticsPagination(limit=limit, offset=offset, total=14, has_more=True),
        )


def test_monthly_plays_endpoint_returns_chart_data() -> None:
    service = StubAnalyticsService()
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/analytics/plays/monthly")

    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {"month": "2026-01", "plays": 2},
            {"month": "2026-02", "plays": 3},
        ]
    }


def test_top_records_endpoint_returns_records_and_forwards_limit() -> None:
    service = StubAnalyticsService()
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/analytics/top-records?limit=7")

    assert response.status_code == 200
    assert response.json() == {
        "records": [
            {
                "release_id": "release-123",
                "discogs_release_id": 555123,
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "thumbnail_url": "https://img.discogs.com/cover.jpg",
                "plays": 5,
                "average_rating": 4.5,
            }
        ]
    }
    assert service.top_calls == [7]


def test_top_records_endpoint_returns_validation_error() -> None:
    service = StubAnalyticsService()
    service.top_error = AnalyticsValidationError("invalid_limit", "limit must be between 1 and 50.")
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/analytics/top-records?limit=0")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_limit",
            "message": "limit must be between 1 and 50.",
        }
    }


def test_distribution_endpoints_return_chart_data() -> None:
    service = StubAnalyticsService()
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        rating_response = client.get("/api/v1/analytics/rating-distribution")
        mood_response = client.get("/api/v1/analytics/mood-distribution")
        style_response = client.get("/api/v1/analytics/style-distribution")

    assert rating_response.status_code == 200
    assert rating_response.json() == {"ratings": {"1": 0, "2": 1, "3": 0, "4": 2, "5": 3}}
    assert mood_response.status_code == 200
    assert mood_response.json() == {"moods": {"Calm": 3, "Focused": 2}}
    assert style_response.status_code == 200
    assert style_response.json() == {"styles": {"Dub Techno": 4, "House": 2}}


def test_month_sessions_endpoint_returns_paged_session_cards() -> None:
    service = StubAnalyticsService()
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/analytics/sessions?month=2026-05&limit=5&offset=5")

    assert response.status_code == 200
    assert response.json() == {
        "sessions": [
            {
                "session_id": "session-123",
                "release_id": "release-123",
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "thumbnail_url": "https://img.discogs.com/cover.jpg",
                "date": "2026-05-12",
                "played_at": "2026-05-12T10:00:00Z",
                "side": "A",
                "rating": 5,
                "mood": "Focused",
                "has_notes": True,
            }
        ],
        "pagination": {"limit": 5, "offset": 5, "total": 12, "has_more": True},
    }
    assert service.month_calls == [("2026-05", 5, 5)]


def test_record_drilldown_endpoints_return_paged_record_counts() -> None:
    service = StubAnalyticsService()
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        rating_response = client.get("/api/v1/analytics/records/by-rating?rating=5&limit=4&offset=2")
        mood_response = client.get("/api/v1/analytics/records/by-mood?mood=Focused&limit=4&offset=2")
        style_response = client.get("/api/v1/analytics/records/by-style?style=Dub%20Techno&limit=4&offset=2")

    expected_json = {
        "records": [
            {
                "release_id": "release-123",
                "discogs_release_id": 555123,
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "thumbnail_url": "https://img.discogs.com/cover.jpg",
                "count": 7,
            }
        ],
        "pagination": {"limit": 4, "offset": 2, "total": 14, "has_more": True},
    }
    assert rating_response.status_code == 200
    assert rating_response.json() == expected_json
    assert mood_response.status_code == 200
    assert mood_response.json() == expected_json
    assert style_response.status_code == 200
    assert style_response.json() == expected_json
    assert service.rating_calls == [(5, 4, 2)]
    assert service.mood_calls == [("Focused", 4, 2)]
    assert service.style_calls == [("Dub Techno", 4, 2)]


def test_drilldown_endpoint_returns_validation_error() -> None:
    service = StubAnalyticsService()
    service.drilldown_error = AnalyticsValidationError("invalid_month", "month must use YYYY-MM format.")
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/analytics/sessions?month=2026-5")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_month",
            "message": "month must use YYYY-MM format.",
        }
    }


def test_drilldown_endpoints_return_empty_pages() -> None:
    service = StubAnalyticsService()
    service.empty_drilldowns = True
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        sessions_response = client.get("/api/v1/analytics/sessions?month=2026-05")
        records_response = client.get("/api/v1/analytics/records/by-rating?rating=5")

    assert sessions_response.status_code == 200
    assert sessions_response.json() == {
        "sessions": [],
        "pagination": {"limit": 10, "offset": 0, "total": 0, "has_more": False},
    }
    assert records_response.status_code == 200
    assert records_response.json() == {
        "records": [],
        "pagination": {"limit": 10, "offset": 0, "total": 0, "has_more": False},
    }


def test_record_drilldown_endpoint_returns_validation_error() -> None:
    service = StubAnalyticsService()
    service.drilldown_error = AnalyticsValidationError("invalid_rating", "rating must be between 1 and 5.")
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/analytics/records/by-rating?rating=6")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_rating",
            "message": "rating must be between 1 and 5.",
        }
    }
