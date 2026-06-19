from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes.analytics import get_analytics_service, get_session_groups_service, get_sessions_service
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
        self.user_id_calls: list[str | None] = []
        self.drilldown_error: Exception | None = None
        self.empty_drilldowns = False
        self.release = SimpleNamespace(
            id="release-123",
            discogs_release_id=555123,
            artist="Boards of Canada",
            title="Music Has The Right To Children",
            year=1998,
            label="System Music (2)",
            catalog_number="WARPLP55",
            cover_image_url="https://img.discogs.com/cover.jpg",
        )
        self.session = SimpleNamespace(
            id="session-123",
            session_group_id="group-123",
            played_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
            vinyl_side="A",
            rating=5,
            mood="Focused",
            notes="Great listen",
        )
        self.tracks = [
            SimpleNamespace(
                track_position="A1",
                track_artist="Boards of Canada",
                track_title="Wildlife Analysis",
                track_duration="1:17",
                track_sequence=1,
            )
        ]

    def get_monthly_plays(self, _db, *, user_id: str | None = None):
        self.user_id_calls.append(user_id)
        return [
            MonthlyPlayCount(month="2026-01", plays=2),
            MonthlyPlayCount(month="2026-02", plays=3),
        ]

    def get_top_records(self, _db, *, limit: int, user_id: str | None = None):
        self.user_id_calls.append(user_id)
        self.top_calls.append(limit)
        if self.top_error is not None:
            raise self.top_error
        return [
            AnalyticsTopRecord(
                release=self.release,
                plays=5,
                average_rating=4.46,
                top_track="Roygbiv",
                top_mood="Focused",
            )
        ]

    def get_sessions_for_month(
        self,
        _db,
        *,
        month: str,
        limit: int,
        offset: int,
        user_id: str | None = None,
    ):
        self.user_id_calls.append(user_id)
        self.month_calls.append((month, limit, offset))
        if self.drilldown_error is not None:
            raise self.drilldown_error
        if self.empty_drilldowns:
            return AnalyticsSessionPage(
                sessions=[],
                pagination=AnalyticsPagination(limit=limit, offset=offset, total=0, has_more=False),
            )
        return AnalyticsSessionPage(
            sessions=[AnalyticsSession(session=self.session, release=self.release, tracks=self.tracks)],
            pagination=AnalyticsPagination(limit=limit, offset=offset, total=12, has_more=True),
        )

    def get_records_for_rating(
        self,
        _db,
        *,
        rating: int,
        limit: int,
        offset: int,
        user_id: str | None = None,
    ):
        self.user_id_calls.append(user_id)
        self.rating_calls.append((rating, limit, offset))
        if self.drilldown_error is not None:
            raise self.drilldown_error
        return self._record_count_page(limit=limit, offset=offset)

    def get_records_for_mood(
        self,
        _db,
        *,
        mood: str,
        limit: int,
        offset: int,
        user_id: str | None = None,
    ):
        self.user_id_calls.append(user_id)
        self.mood_calls.append((mood, limit, offset))
        if self.drilldown_error is not None:
            raise self.drilldown_error
        return self._record_count_page(limit=limit, offset=offset)

    def get_records_for_style(
        self,
        _db,
        *,
        style: str,
        limit: int,
        offset: int,
        user_id: str | None = None,
    ):
        self.user_id_calls.append(user_id)
        self.style_calls.append((style, limit, offset))
        if self.drilldown_error is not None:
            raise self.drilldown_error
        return self._record_count_page(limit=limit, offset=offset)

    def get_rating_distribution(self, _db, *, user_id: str | None = None):
        self.user_id_calls.append(user_id)
        return {"1": 0, "2": 1, "3": 0, "4": 2, "5": 3}

    def get_mood_distribution(self, _db, *, user_id: str | None = None):
        self.user_id_calls.append(user_id)
        return {"Calm": 3, "Focused": 2}

    def get_style_distribution(self, _db, *, user_id: str | None = None):
        self.user_id_calls.append(user_id)
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


class StubSessionGroupsService:
    def __init__(self) -> None:
        self.get_by_ids_calls: list[list[str]] = []
        self.group = SimpleNamespace(
            id="group-123",
            title="Late night stack",
            status="completed",
            style_focus="one_style",
            mood_direction="mood_switch",
            session_type="rediscovery",
            notes=None,
            started_at=datetime(2026, 5, 12, 9, 0, tzinfo=UTC),
            ended_at=datetime(2026, 5, 12, 10, 30, tzinfo=UTC),
        )

    def get_session_groups_by_ids(self, _db, session_group_ids: list[str], *, user_id: str | None = None):
        _ = user_id
        self.get_by_ids_calls.append(session_group_ids)
        return [self.group] if self.group.id in session_group_ids else []

    def can_edit_session_group(self, _session_group) -> bool:
        return False

    def editable_until(self, _session_group):
        return datetime(2026, 5, 12, 10, 45, tzinfo=UTC)


class StubSessionsService:
    def __init__(self) -> None:
        self.track_calls: list[list[tuple[str, object]]] = []

    def get_tracks_by_session_ids_for_releases(self, _db, session_releases: list[tuple[str, object]]):
        self.track_calls.append(session_releases)
        return {
            session_id: [
                SimpleNamespace(
                    track_position="A1",
                    track_artist="Boards of Canada",
                    track_title="Wildlife Analysis",
                    track_duration="1:17",
                    track_sequence=1,
                )
            ]
            for session_id, _release in session_releases
        }


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
                "top_track": "Roygbiv",
                "top_mood": "Focused",
            }
        ]
    }
    assert service.top_calls == [7]


def test_top_records_endpoint_returns_validation_error() -> None:
    service = StubAnalyticsService()
    service.top_error = AnalyticsValidationError("invalid_limit", "limit must be between 1 and 250.")
    app.dependency_overrides[get_analytics_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/analytics/top-records?limit=0")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_limit",
            "message": "limit must be between 1 and 250.",
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
    session_groups_service = StubSessionGroupsService()
    sessions_service = StubSessionsService()
    app.dependency_overrides[get_analytics_service] = lambda: service
    app.dependency_overrides[get_session_groups_service] = lambda: session_groups_service
    app.dependency_overrides[get_sessions_service] = lambda: sessions_service

    with TestClient(app) as client:
        response = client.get("/api/v1/analytics/sessions?month=2026-05&limit=5&offset=5")

    assert response.status_code == 200
    assert response.json() == {
        "sessions": [
            {
                "session_id": "session-123",
                "release_id": "release-123",
                "session_group_id": "group-123",
                "session_group": {
                    "id": "group-123",
                    "title": "Late night stack",
                    "status": "completed",
                    "style_focus": "one_style",
                    "mood_direction": "mood_switch",
                    "session_type": "rediscovery",
                    "notes": None,
                    "started_at": "2026-05-12T09:00:00Z",
                    "ended_at": "2026-05-12T10:30:00Z",
                    "can_edit": False,
                    "editable_until": "2026-05-12T10:45:00Z",
                },
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "year": 1998,
                "label": "System Music",
                "catalog_number": "WARPLP55",
                "thumbnail_url": "https://img.discogs.com/cover.jpg",
                "date": "2026-05-12",
                "played_at": "2026-05-12T10:00:00Z",
                "side": "A",
                "tracks": [
                    {
                        "position": "A1",
                        "artist": "Boards of Canada",
                        "title": "Wildlife Analysis",
                        "duration": "1:17",
                        "sequence": 1,
                    }
                ],
                "rating": 5,
                "mood": "Focused",
                "has_notes": True,
            }
        ],
        "pagination": {"limit": 5, "offset": 5, "total": 12, "has_more": True},
    }
    assert service.month_calls == [("2026-05", 5, 5)]
    assert session_groups_service.get_by_ids_calls == [["group-123"]]
    assert sessions_service.track_calls[0][0][0] == "session-123"


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
