from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.routes.releases import get_sessions_service as get_release_sessions_service
from app.api.routes.sessions import get_sessions_service
from app.main import app
from app.services.sessions_service import (
    CreateSessionResult,
    ReleaseNotFoundError,
    SessionNotFoundError,
    SessionValidationError,
)


@dataclass
class SessionStub:
    id: str
    release_id: str
    rating: int | None
    mood: str | None
    notes: str | None
    played_at: datetime | None
    vinyl_side: str | None
    created_at: datetime


class StubSessionsService:
    def __init__(self) -> None:
        self.create_error: Exception | None = None
        self.get_error: Exception | None = None
        self.list_error: Exception | None = None
        self.create_calls: list[dict] = []
        self.get_calls: list[str] = []
        self.list_calls: list[tuple[str, int, int]] = []
        self.created_result = CreateSessionResult(
            session_id="session-123",
            timestamp=datetime(2026, 4, 19, 8, 30, tzinfo=UTC),
        )
        self.session = SessionStub(
            id="session-123",
            release_id="release-123",
            rating=5,
            mood="Calm",
            notes="Great pressing.",
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side="A",
            created_at=datetime(2026, 4, 19, 8, 30, tzinfo=UTC),
        )
        self.release_sessions = [
            SessionStub(
                id="session-123",
                release_id="release-123",
                rating=5,
                mood="Calm",
                notes="Great pressing.",
                played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
                vinyl_side="A",
                created_at=datetime(2026, 4, 19, 8, 30, tzinfo=UTC),
            ),
            SessionStub(
                id="session-456",
                release_id="release-123",
                rating=4,
                mood=None,
                notes=None,
                played_at=datetime(2026, 3, 10, 14, 0, tzinfo=UTC),
                vinyl_side="B",
                created_at=datetime(2026, 4, 18, 8, 30, tzinfo=UTC),
            ),
        ]

    def create_session(self, _db, **kwargs) -> CreateSessionResult:
        self.create_calls.append(kwargs)
        if self.create_error is not None:
            raise self.create_error
        return self.created_result

    def get_session(self, _db, session_id: str) -> SessionStub:
        self.get_calls.append(session_id)
        if self.get_error is not None:
            raise self.get_error
        return self.session

    def get_sessions_by_release(self, _db, release_id: str, *, limit: int, offset: int) -> list[SessionStub]:
        self.list_calls.append((release_id, limit, offset))
        if self.list_error is not None:
            raise self.list_error
        return self.release_sessions[offset : offset + limit]


def override_sessions_service(service: StubSessionsService) -> None:
    app.dependency_overrides[get_sessions_service] = lambda: service
    app.dependency_overrides[get_release_sessions_service] = lambda: service


def clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_create_session_endpoint_returns_201() -> None:
    service = StubSessionsService()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions",
            json={
                "release_id": "release-123",
                "side": "A",
                "rating": 5,
                "mood": "Calm",
                "notes": "Great pressing.",
                "played_at": "2026-03-14T19:21:00Z",
            },
        )

    clear_overrides()

    assert response.status_code == 201
    assert response.json() == {
        "session_id": "session-123",
        "timestamp": "2026-04-19T08:30:00Z",
        "status": "success",
    }
    assert service.create_calls == [
        {
            "release_id": "release-123",
            "rating": 5,
            "mood": "Calm",
            "notes": "Great pressing.",
            "played_at": "2026-03-14T19:21:00Z",
            "side": "A",
        }
    ]


def test_create_session_endpoint_returns_standardized_validation_error() -> None:
    service = StubSessionsService()
    service.create_error = SessionValidationError("invalid_rating", "Rating must be between 1 and 5.")
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions",
            json={
                "release_id": "release-123",
                "rating": 6,
                "played_at": "2026-03-14T19:21:00Z",
            },
        )

    clear_overrides()

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_rating",
            "message": "Rating must be between 1 and 5.",
        }
    }


def test_get_session_endpoint_returns_session_details() -> None:
    service = StubSessionsService()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/session-123")

    clear_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "id": "session-123",
        "release_id": "release-123",
        "rating": 5,
        "mood": "Calm",
        "notes": "Great pressing.",
        "played_at": "2026-03-14T19:21:00Z",
        "vinyl_side": "A",
        "created_at": "2026-04-19T08:30:00Z",
    }


def test_get_session_endpoint_returns_404_when_missing() -> None:
    service = StubSessionsService()
    service.get_error = SessionNotFoundError("missing-session")
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/missing-session")

    clear_overrides()

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "session_not_found",
            "message": "Session 'missing-session' was not found.",
        }
    }


def test_get_release_sessions_endpoint_returns_paginated_history() -> None:
    service = StubSessionsService()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/release-123/sessions?limit=1&offset=1")

    clear_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "sessions": [
            {
                "session_id": "session-456",
                "date": "2026-03-10",
                "side": "B",
                "rating": 4,
                "mood": None,
                "has_notes": False,
            }
        ]
    }
    assert service.list_calls == [("release-123", 1, 1)]


def test_get_release_sessions_endpoint_returns_404_for_missing_release() -> None:
    service = StubSessionsService()
    service.list_error = ReleaseNotFoundError("missing-release")
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/missing-release/sessions")

    clear_overrides()

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "release_not_found",
            "message": "Release 'missing-release' was not found.",
        }
    }


def test_create_session_endpoint_formats_request_validation_errors() -> None:
    service = StubSessionsService()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions",
            json={"release_id": "release-123"},
        )

    clear_overrides()

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "Field required",
        }
    }
