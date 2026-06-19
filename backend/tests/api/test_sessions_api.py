from fastapi.testclient import TestClient

from app.main import app
from app.services.session_groups_service import (
    SessionGroupAlreadyActiveError,
    SessionGroupNotFoundError,
)
from app.services.sessions_service import (
    ReleaseNotFoundError,
    SessionEditWindowExpiredError,
    SessionMoodAlreadyExistsError,
    SessionNotFoundError,
    SessionValidationError,
)


def expected_session_group_json(
    *,
    status: str = "active",
    ended_at: str | None = None,
    updated_at: str = "2026-04-19T08:00:00Z",
    style_focus: str = "mixed",
    mood_direction: str = "steady_mood",
    session_type: str = "casual_listening",
    notes: str | None = None,
    can_edit: bool = True,
    editable_until: str | None = None,
) -> dict:
    return {
        "id": "group-123",
        "title": "Late night stack",
        "status": status,
        "style_focus": style_focus,
        "mood_direction": mood_direction,
        "session_type": session_type,
        "notes": notes,
        "started_at": "2026-04-19T08:00:00Z",
        "ended_at": ended_at,
        "created_at": "2026-04-19T08:00:00Z",
        "updated_at": updated_at,
        "can_edit": can_edit,
        "editable_until": editable_until,
    }


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
        "session_group_id": None,
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
            "track_positions": None,
            "session_group_id": None,
        }
    ]


def test_start_session_group_endpoint_returns_created_group(
    build_stub_session_groups_service,
    override_session_groups_service,
) -> None:
    service = build_stub_session_groups_service()
    override_session_groups_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions/groups",
            json={
                "title": "  Late night stack  ",
                "started_at": "2026-04-19T08:00:00Z",
                "style_focus": "one_style",
                "mood_direction": "energy_build",
                "session_type": "dj_set",
                "notes": "Warm up shelf.",
            },
        )

    assert response.status_code == 201
    assert response.json() == expected_session_group_json(
        style_focus="one_style",
        mood_direction="energy_build",
        session_type="dj_set",
        notes="Warm up shelf.",
    )
    assert service.start_calls == [
        {
            "title": "  Late night stack  ",
            "started_at": "2026-04-19T08:00:00Z",
            "style_focus": "one_style",
            "mood_direction": "energy_build",
            "session_type": "dj_set",
            "notes": "Warm up shelf.",
        }
    ]


def test_start_session_group_endpoint_returns_conflict_when_group_is_active(
    build_stub_session_groups_service,
    override_session_groups_service,
) -> None:
    service = build_stub_session_groups_service()
    service.start_error = SessionGroupAlreadyActiveError("group-123")
    override_session_groups_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/sessions/groups", json={"title": None})

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "session_group_active",
            "message": "A timed listening session is already active.",
        }
    }


def test_get_active_session_group_endpoint_returns_active_group(
    build_stub_session_groups_service,
    override_session_groups_service,
) -> None:
    service = build_stub_session_groups_service()
    override_session_groups_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/groups/active")

    assert response.status_code == 200
    assert response.json() == {"session_group": expected_session_group_json()}


def test_get_active_session_group_endpoint_returns_null_when_none_active(
    build_stub_session_groups_service,
    override_session_groups_service,
) -> None:
    service = build_stub_session_groups_service()
    service.active_group = None
    override_session_groups_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/groups/active")

    assert response.status_code == 200
    assert response.json() == {"session_group": None}


def test_finish_session_group_endpoint_returns_completed_group(
    build_stub_session_groups_service,
    override_session_groups_service,
) -> None:
    service = build_stub_session_groups_service()
    override_session_groups_service(service)

    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/sessions/groups/group-123/finish",
            json={
                "ended_at": "2026-04-19T09:00:00Z",
                "style_focus": "random",
                "mood_direction": "cool_down",
                "session_type": "background",
                "notes": "Soft finish.",
            },
        )

    assert response.status_code == 200
    assert response.json() == expected_session_group_json(
        status="completed",
        ended_at="2026-04-19T09:00:00Z",
        updated_at="2026-04-19T09:00:00Z",
        style_focus="random",
        mood_direction="cool_down",
        session_type="background",
        notes="Soft finish.",
        editable_until="2026-04-19T09:15:00Z",
    )
    assert service.finish_calls == [
        ("group-123", "2026-04-19T09:00:00Z", "random", "cool_down", "background", "Soft finish.")
    ]


def test_update_session_group_endpoint_returns_updated_group(
    build_stub_session_groups_service,
    override_session_groups_service,
) -> None:
    service = build_stub_session_groups_service()
    service.group.status = "completed"
    service.group.ended_at = service.group.updated_at.replace(hour=9)
    service.group.updated_at = service.group.ended_at
    override_session_groups_service(service)

    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/sessions/groups/group-123",
            json={
                "style_focus": "random",
                "mood_direction": "cool_down",
                "session_type": "background",
                "notes": "Soft finish.",
            },
        )

    assert response.status_code == 200
    assert response.json() == expected_session_group_json(
        status="completed",
        ended_at="2026-04-19T09:00:00Z",
        updated_at="2026-04-19T09:00:00Z",
        style_focus="random",
        mood_direction="cool_down",
        session_type="background",
        notes="Soft finish.",
        editable_until="2026-04-19T09:15:00Z",
    )
    assert service.update_calls == [
        (
            "group-123",
            {
                "style_focus": "random",
                "mood_direction": "cool_down",
                "session_type": "background",
                "notes": "Soft finish.",
            },
        )
    ]


def test_get_session_group_endpoint_returns_404_when_missing(
    build_stub_session_groups_service,
    override_session_groups_service,
) -> None:
    service = build_stub_session_groups_service()
    service.get_error = SessionGroupNotFoundError("missing-group")
    override_session_groups_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/groups/missing-group")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "session_group_not_found",
            "message": "Session group 'missing-group' was not found.",
        }
    }


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
        "session_group_id": None,
        "rating": 5,
        "mood": "Calm",
        "notes": "Great pressing.",
        "played_at": "2026-03-14T19:21:00Z",
        "vinyl_side": "A",
        "tracks": [
            {
                "position": "A1",
                "artist": "Boards of Canada",
                "title": "Wildlife Analysis",
                "duration": "1:17",
                "sequence": 1,
            }
        ],
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
                "track_positions": ["B1"],
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": "session-123",
        "release_id": "release-123",
        "session_group_id": None,
        "rating": 4,
        "mood": "Focused",
        "notes": "Changed after replay.",
        "played_at": "2026-03-14T19:21:00Z",
        "vinyl_side": "B",
        "tracks": [
            {
                "position": "B1",
                "artist": None,
                "title": "Track B1",
                "duration": None,
                "sequence": 1,
            }
        ],
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
                "track_positions": ["B1"],
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
                "session_group_id": None,
                "session_group": None,
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "year": 1998,
                "label": "Warp Records",
                "catalog_number": "WARPLP55",
                "thumbnail_url": "https://img.discogs.com/cover.jpg",
                "date": "2026-03-14",
                "played_at": "2026-03-14T19:21:00Z",
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


def test_get_home_summary_endpoint_includes_recent_session_group_metadata(
    build_stub_sessions_service,
    build_stub_session_groups_service,
    override_sessions_service,
    override_session_groups_service,
) -> None:
    sessions_service = build_stub_sessions_service()
    sessions_service.release_sessions[0].session_group_id = "group-123"
    session_groups_service = build_stub_session_groups_service()
    session_groups_service.group.status = "completed"
    session_groups_service.group.style_focus = "one_style"
    session_groups_service.group.mood_direction = "mood_switch"
    session_groups_service.group.session_type = "rediscovery"
    session_groups_service.group.ended_at = session_groups_service.group.updated_at.replace(hour=9)
    override_sessions_service(sessions_service)
    override_session_groups_service(session_groups_service)

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/summary")

    assert response.status_code == 200
    recent_session = response.json()["recent_sessions"][0]
    assert recent_session["session_group"] == {
        "id": "group-123",
        "title": "Late night stack",
        "status": "completed",
        "style_focus": "one_style",
        "mood_direction": "mood_switch",
        "session_type": "rediscovery",
        "notes": None,
        "started_at": "2026-04-19T08:00:00Z",
        "ended_at": "2026-04-19T09:00:00Z",
        "can_edit": True,
        "editable_until": "2026-04-19T09:15:00Z",
    }
    assert session_groups_service.get_by_ids_calls == [["group-123"]]


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
    assert service.user_id_calls == ["test-user"]


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
    assert service.create_mood_calls == [("Dubby", "test-user")]


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
    assert service.delete_mood_calls == [("Dubby", "test-user")]


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
                "session_group_id": None,
                "date": "2026-03-14",
                "played_at": "2026-03-14T19:21:00Z",
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
