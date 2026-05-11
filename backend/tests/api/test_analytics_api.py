from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes.analytics import get_analytics_service
from app.main import app
from app.services.analytics_service import AnalyticsTopRecord, AnalyticsValidationError, MonthlyPlayCount


class StubAnalyticsService:
    def __init__(self) -> None:
        self.top_calls: list[int] = []
        self.top_error: Exception | None = None
        self.release = SimpleNamespace(
            id="release-123",
            discogs_release_id=555123,
            artist="Boards of Canada",
            title="Music Has The Right To Children",
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

    def get_rating_distribution(self, _db):
        return {"1": 0, "2": 1, "3": 0, "4": 2, "5": 3}

    def get_mood_distribution(self, _db):
        return {"Calm": 3, "Focused": 2}


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

    assert rating_response.status_code == 200
    assert rating_response.json() == {"ratings": {"1": 0, "2": 1, "3": 0, "4": 2, "5": 3}}
    assert mood_response.status_code == 200
    assert mood_response.json() == {"moods": {"Calm": 3, "Focused": 2}}
