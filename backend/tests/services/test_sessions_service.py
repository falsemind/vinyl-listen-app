from datetime import UTC, datetime

import pytest

from app.models.sessions import Sessions
from app.services.sessions_service import (
    ReleaseNotFoundError,
    SessionNotFoundError,
    SessionValidationError,
)


def test_create_session_persists_validated_session(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    service = build_sessions_service(
        sessions_repository=repository,
        payload_by_discogs_id={
            555123: {
                "tracklist": [
                    {"position": "A1"},
                    {"position": "A2"},
                    {"position": "B1"},
                ]
            }
        },
    )

    result = service.create_session(
        db=object(),
        release_id="release-123",
        rating=5,
        mood="  Calm  ",
        notes="  Great pressing.  ",
        played_at="2026-03-14T19:21:00Z",
        side="a",
    )

    assert result.session_id == "session-123"
    assert result.status == "success"
    assert repository.created_payload == {
        "release_id": "release-123",
        "rating": 5,
        "mood": "Calm",
        "notes": "Great pressing.",
        "played_at": datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
        "vinyl_side": "A",
    }


@pytest.mark.parametrize("rating", [0, 6])
def test_create_session_rejects_invalid_rating(rating: int, build_sessions_service) -> None:
    service = build_sessions_service()

    with pytest.raises(SessionValidationError) as exc_info:
        service.create_session(
            db=object(),
            release_id="release-123",
            rating=rating,
            mood=None,
            notes=None,
            played_at="2026-03-14T19:21:00Z",
            side=None,
        )

    assert exc_info.value.code == "invalid_rating"


def test_create_session_rejects_invalid_side(build_sessions_service) -> None:
    service = build_sessions_service(
        payload_by_discogs_id={
            555123: {
                "tracklist": [
                    {"position": "A1"},
                    {"position": "B1"},
                ]
            }
        }
    )

    with pytest.raises(SessionValidationError) as exc_info:
        service.create_session(
            db=object(),
            release_id="release-123",
            rating=4,
            mood=None,
            notes=None,
            played_at="2026-03-14T19:21:00Z",
            side="D",
        )

    assert exc_info.value.code == "invalid_side"


def test_create_session_accepts_side_when_release_sides_are_unknown(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    service = build_sessions_service(sessions_repository=repository)

    service.create_session(
        db=object(),
        release_id="release-123",
        rating=4,
        mood=None,
        notes=None,
        played_at="2026-03-14T19:21:00Z",
        side="A",
    )

    assert repository.created_payload is not None
    assert repository.created_payload["vinyl_side"] == "A"


def test_create_session_accepts_repeated_side_option_value(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    service = build_sessions_service(
        sessions_repository=repository,
        payload_by_discogs_id={
            555123: {
                "tracklist": [
                    {"position": "X1"},
                    {"position": "Y1"},
                    {"position": "X1"},
                    {"position": "Y1"},
                ]
            }
        },
    )

    service.create_session(
        db=object(),
        release_id="release-123",
        rating=4,
        mood=None,
        notes=None,
        played_at="2026-03-14T19:21:00Z",
        side="2:X",
    )

    assert repository.created_payload is not None
    assert repository.created_payload["vinyl_side"] == "2:X"


def test_create_session_rejects_invalid_played_at(build_sessions_service) -> None:
    service = build_sessions_service()

    with pytest.raises(SessionValidationError) as exc_info:
        service.create_session(
            db=object(),
            release_id="release-123",
            rating=4,
            mood=None,
            notes=None,
            played_at="not-a-datetime",
            side=None,
        )

    assert exc_info.value.code == "invalid_played_at"


def test_create_session_rejects_unknown_release(build_sessions_service) -> None:
    service = build_sessions_service(releases=[])

    with pytest.raises(ReleaseNotFoundError):
        service.create_session(
            db=object(),
            release_id="missing-release",
            rating=4,
            mood=None,
            notes=None,
            played_at="2026-03-14T19:21:00Z",
            side=None,
        )


def test_get_session_returns_existing_session(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    repository.sessions.append(
        Sessions(
            id="session-123",
            release_id="release-123",
            rating=5,
            mood="Calm",
            notes="Great pressing.",
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side="A",
            created_at=datetime(2026, 4, 19, tzinfo=UTC),
        )
    )
    service = build_sessions_service(sessions_repository=repository)

    session = service.get_session(db=object(), session_id="session-123")

    assert session.id == "session-123"


def test_get_session_raises_for_missing_session(build_sessions_service) -> None:
    service = build_sessions_service()

    with pytest.raises(SessionNotFoundError):
        service.get_session(db=object(), session_id="missing-session")


def test_get_sessions_by_release_enforces_pagination_rules(build_sessions_service) -> None:
    service = build_sessions_service()

    with pytest.raises(SessionValidationError) as exc_info:
        service.get_sessions_by_release(db=object(), release_id="release-123", limit=0, offset=0)

    assert exc_info.value.code == "invalid_pagination"


def test_get_sessions_by_release_returns_paginated_results(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    repository.sessions.extend(
        [
            Sessions(
                id="session-1",
                release_id="release-123",
                rating=5,
                mood="Calm",
                notes=None,
                played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
                vinyl_side="A",
                created_at=datetime(2026, 4, 19, tzinfo=UTC),
            ),
            Sessions(
                id="session-2",
                release_id="release-123",
                rating=4,
                mood=None,
                notes="Nice",
                played_at=datetime(2026, 3, 13, 19, 21, tzinfo=UTC),
                vinyl_side="B",
                created_at=datetime(2026, 4, 18, tzinfo=UTC),
            ),
        ]
    )
    service = build_sessions_service(sessions_repository=repository)

    sessions = service.get_sessions_by_release(
        db=object(),
        release_id="release-123",
        limit=1,
        offset=1,
    )

    assert [session.id for session in sessions] == ["session-2"]


def test_custom_moods_are_persisted_and_listed(
    sessions_moods_repository_factory,
    build_sessions_service,
) -> None:
    moods_repository = sessions_moods_repository_factory()
    service = build_sessions_service(moods_repository=moods_repository)

    created = service.create_custom_mood(db=object(), name="  Late   Night  ")
    duplicate = service.create_custom_mood(db=object(), name="late night")

    assert created.name == "Late Night"
    assert duplicate.name == "Late Night"
    assert [mood.name for mood in service.list_custom_moods(db=object())] == ["Late Night"]


@pytest.mark.parametrize("name", ["Lo", "This Mood Name Is Too Long", "Dreamy!"])
def test_create_custom_mood_rejects_invalid_names(name: str, build_sessions_service) -> None:
    service = build_sessions_service()

    with pytest.raises(SessionValidationError) as exc_info:
        service.create_custom_mood(db=object(), name=name)

    assert exc_info.value.code == "invalid_mood"


def test_delete_custom_mood_removes_saved_option(
    sessions_moods_repository_factory,
    build_sessions_service,
) -> None:
    moods_repository = sessions_moods_repository_factory()
    service = build_sessions_service(moods_repository=moods_repository)
    service.create_custom_mood(db=object(), name="Dubby")

    service.delete_custom_mood(db=object(), name="dubby")

    assert service.list_custom_moods(db=object()) == []
