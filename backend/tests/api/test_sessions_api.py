from fastapi.testclient import TestClient

from app.main import app
from app.services.sessions_service import (
    ReleaseNotFoundError,
    SessionNotFoundError,
    SessionValidationError,
)


def test_create_session_endpoint_returns_201(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
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


def test_create_session_endpoint_returns_standardized_validation_error(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
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

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_rating",
            "message": "Rating must be between 1 and 5.",
        }
    }


def test_get_session_endpoint_returns_session_details(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/session-123")

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


def test_get_session_endpoint_returns_404_when_missing(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    service.get_error = SessionNotFoundError("missing-session")
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/missing-session")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "session_not_found",
            "message": "Session 'missing-session' was not found.",
        }
    }


def test_get_home_summary_endpoint_returns_real_session_data(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/summary")

    assert response.status_code == 200
    assert response.json() == {
        "recent_sessions": [
            {
                "session_id": "session-123",
                "release_id": "release-123",
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "date": "2026-03-14",
                "side": "A",
                "rating": 5,
                "mood": "Calm",
                "has_notes": True,
            }
        ],
        "total_sessions": 2,
        "records_this_month": 1,
        "top_records": [
            {
                "release_id": "release-123",
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "plays": 2,
                "average_rating": 4.5,
            }
        ],
    }
    assert service.summary_calls == [(5, 3)]


def test_get_release_sessions_endpoint_returns_paginated_history(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/release-123/sessions?limit=1&offset=1")

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


def test_get_release_sessions_endpoint_returns_404_for_missing_release(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    service.list_error = ReleaseNotFoundError("missing-release")
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/missing-release/sessions")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "release_not_found",
            "message": "Release 'missing-release' was not found.",
        }
    }


def test_create_session_endpoint_formats_request_validation_errors(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions",
            json={"release_id": "release-123"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "Field required",
        }
    }
