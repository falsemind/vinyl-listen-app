from fastapi.testclient import TestClient

from app.main import app
from app.services.sessions_service import (
    ReleaseNotFoundError,
    SessionEditWindowExpiredError,
    SessionMoodAlreadyExistsError,
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
        "can_edit": True,
        "editable_until": "2026-04-19T08:45:00Z",
    }


def test_update_session_endpoint_returns_updated_session(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/sessions/session-123",
            json={
                "side": "B",
                "rating": 4,
                "mood": "Focused",
                "notes": "Changed after replay.",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": "session-123",
        "release_id": "release-123",
        "rating": 4,
        "mood": "Focused",
        "notes": "Changed after replay.",
        "played_at": "2026-03-14T19:21:00Z",
        "vinyl_side": "B",
        "created_at": "2026-04-19T08:30:00Z",
        "can_edit": True,
        "editable_until": "2026-04-19T08:45:00Z",
    }
    assert service.update_calls == [
        (
            "session-123",
            {
                "side": "B",
                "rating": 4,
                "mood": "Focused",
                "notes": "Changed after replay.",
            },
        )
    ]


def test_update_session_endpoint_returns_expired_window_error(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    service.update_error = SessionEditWindowExpiredError("session-123")
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.patch("/api/v1/sessions/session-123", json={"rating": 4})

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "session_edit_window_expired",
            "message": "Session can only be edited for 15 minutes after it is created.",
        }
    }


def test_update_session_endpoint_returns_validation_error(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    service.update_error = SessionValidationError("invalid_rating", "Rating must be between 1 and 5.")
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.patch("/api/v1/sessions/session-123", json={"rating": 6})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_rating",
            "message": "Rating must be between 1 and 5.",
        }
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
                "thumbnail_url": "https://img.discogs.com/cover.jpg",
                "date": "2026-03-14",
                "played_at": "2026-03-14T19:21:00Z",
                "side": "A",
                "rating": 5,
                "mood": "Calm",
                "has_notes": True,
                "created_at": "2026-04-19T08:30:00Z",
                "can_edit": True,
                "editable_until": "2026-04-19T08:45:00Z",
            }
        ],
        "total_sessions": 2,
        "records_this_month": 1,
        "top_records": [
            {
                "release_id": "release-123",
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "thumbnail_url": "https://img.discogs.com/cover.jpg",
                "plays": 2,
                "average_rating": 4.5,
            }
        ],
    }
    assert service.summary_calls == [(5, 3)]


def test_get_custom_moods_endpoint_returns_saved_moods(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/moods")

    assert response.status_code == 200
    assert response.json() == {
        "moods": [
            {"name": "Dubby", "is_custom": True},
            {"name": "Late Night", "is_custom": True},
        ]
    }


def test_create_custom_mood_endpoint_returns_created_mood(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/sessions/moods", json={"name": "Dubby"})

    assert response.status_code == 201
    assert response.json() == {"mood": {"name": "Dubby", "is_custom": True}}
    assert service.create_mood_calls == ["Dubby"]


def test_create_custom_mood_endpoint_returns_validation_error(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    service.mood_error = SessionValidationError("invalid_mood", "Mood name must use only letters, numbers, and spaces.")
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/sessions/moods", json={"name": "Dubby!"})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_mood",
            "message": "Mood name must use only letters, numbers, and spaces.",
        }
    }


def test_create_custom_mood_endpoint_returns_conflict_for_duplicate(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    service.mood_error = SessionMoodAlreadyExistsError("Dubby")
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/sessions/moods", json={"name": "Dubby"})

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "duplicate_mood",
            "message": "Mood already exists.",
        }
    }


def test_delete_custom_mood_endpoint_deletes_saved_mood(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.delete("/api/v1/sessions/moods/Dubby")

    assert response.status_code == 204
    assert service.delete_mood_calls == ["Dubby"]


def test_get_release_sessions_endpoint_returns_paginated_history(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/release-123/sessions?limit=1&offset=0")

    assert response.status_code == 200
    assert response.json() == {
        "sessions": [
            {
                "session_id": "session-123",
                "date": "2026-03-14",
                "played_at": "2026-03-14T19:21:00Z",
                "side": "A",
                "rating": 5,
                "mood": "Calm",
                "notes": "Great pressing.",
                "has_notes": True,
                "created_at": "2026-04-19T08:30:00Z",
                "can_edit": True,
                "editable_until": "2026-04-19T08:45:00Z",
            }
        ]
    }
    assert service.list_calls == [("release-123", 1, 0)]


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
