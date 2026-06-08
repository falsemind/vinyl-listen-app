from datetime import UTC, datetime, timedelta

import pytest

from app.models.sessions import Sessions
from app.services.sessions_service import (
    ReleaseNotFoundError,
    SessionEditWindowExpiredError,
    SessionMoodAlreadyExistsError,
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


def test_create_session_saves_selected_tracks_for_side(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    service = build_sessions_service(
        sessions_repository=repository,
        payload_by_discogs_id={
            555123: {
                "tracklist": [
                    {"position": "A1", "type_": "track", "title": "Intro", "duration": "1:00"},
                    {"position": "A2", "type_": "track", "title": "Main Tune", "duration": ""},
                    {"position": "B1", "type_": "track", "title": "Flip", "duration": "2:00"},
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
        side="A",
        track_positions=["A2", "A1"],
    )

    tracks = repository.get_tracks_by_session_id(object(), "session-123")
    track_summaries = [
        (track.track_position, track.track_title, track.track_duration, track.track_sequence) for track in tracks
    ]
    assert track_summaries == [
        ("A1", "Intro", "1:00", 1),
        ("A2", "Main Tune", None, 2),
    ]


def test_create_session_rejects_track_from_another_side(build_sessions_service) -> None:
    service = build_sessions_service(
        payload_by_discogs_id={
            555123: {
                "tracklist": [
                    {"position": "A1", "type_": "track", "title": "Intro"},
                    {"position": "B1", "type_": "track", "title": "Flip"},
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
            side="A",
            track_positions=["B1"],
        )

    assert exc_info.value.code == "invalid_tracks"


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


def test_update_session_persists_changes_within_edit_window(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    created_at = datetime(2026, 4, 19, 8, 30, tzinfo=UTC)
    repository.sessions.append(
        Sessions(
            id="session-123",
            release_id="release-123",
            rating=5,
            mood="Calm",
            notes="Great pressing.",
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side="A",
            created_at=created_at,
        )
    )
    service = build_sessions_service(
        sessions_repository=repository,
        now_provider=lambda: created_at + timedelta(minutes=10),
    )

    session = service.update_session(
        db=object(),
        session_id="session-123",
        fields={"rating": 4, "mood": " focused ", "notes": "  Replayed side B.  ", "side": "b"},
    )

    assert session.rating == 4
    assert session.mood == "Focused"
    assert session.notes == "Replayed side B."
    assert session.vinyl_side == "B"
    assert repository.updated_payload == {
        "rating": 4,
        "mood": "Focused",
        "notes": "Replayed side B.",
        "vinyl_side": "B",
    }


def test_update_session_replaces_selected_tracks(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    created_at = datetime(2026, 4, 19, 8, 30, tzinfo=UTC)
    repository.sessions.append(
        Sessions(
            id="session-123",
            release_id="release-123",
            rating=5,
            mood="Calm",
            notes="Great pressing.",
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side="A",
            created_at=created_at,
        )
    )
    service = build_sessions_service(
        sessions_repository=repository,
        payload_by_discogs_id={
            555123: {
                "tracklist": [
                    {"position": "A1", "type_": "track", "title": "Intro"},
                    {"position": "A2", "type_": "track", "title": "Main Tune"},
                ]
            }
        },
        now_provider=lambda: created_at + timedelta(minutes=10),
    )

    service.update_session(
        db=object(),
        session_id="session-123",
        fields={"track_positions": ["A2"]},
    )

    tracks = repository.get_tracks_by_session_id(object(), "session-123")
    assert [(track.track_position, track.track_title, track.track_sequence) for track in tracks] == [
        ("A2", "Main Tune", 2)
    ]


def test_update_session_can_clear_optional_fields(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    created_at = datetime(2026, 4, 19, 8, 30, tzinfo=UTC)
    repository.sessions.append(
        Sessions(
            id="session-123",
            release_id="release-123",
            rating=5,
            mood="Calm",
            notes="Great pressing.",
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side="A",
            created_at=created_at,
        )
    )
    service = build_sessions_service(
        sessions_repository=repository,
        now_provider=lambda: created_at + timedelta(minutes=3),
    )

    session = service.update_session(
        db=object(),
        session_id="session-123",
        fields={"rating": None, "mood": None, "notes": None, "side": None},
    )

    assert session.rating is None
    assert session.mood is None
    assert session.notes is None
    assert session.vinyl_side is None


def test_update_session_rejects_expired_edit_window(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    created_at = datetime(2026, 4, 19, 8, 30, tzinfo=UTC)
    repository.sessions.append(
        Sessions(
            id="session-123",
            release_id="release-123",
            rating=5,
            mood="Calm",
            notes="Great pressing.",
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side="A",
            created_at=created_at,
        )
    )
    service = build_sessions_service(
        sessions_repository=repository,
        now_provider=lambda: created_at + timedelta(minutes=16),
    )

    with pytest.raises(SessionValidationError) as exc_info:
        service.update_session(db=object(), session_id="session-123", fields={})

    assert exc_info.value.code == "invalid_request"

    with pytest.raises(SessionEditWindowExpiredError) as expired_exc:
        service.update_session(db=object(), session_id="session-123", fields={"rating": 4})

    assert expired_exc.value.code == "session_edit_window_expired"


def test_update_session_rejects_invalid_rating(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    created_at = datetime(2026, 4, 19, 8, 30, tzinfo=UTC)
    repository.sessions.append(
        Sessions(
            id="session-123",
            release_id="release-123",
            rating=5,
            mood="Calm",
            notes="Great pressing.",
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side="A",
            created_at=created_at,
        )
    )
    service = build_sessions_service(
        sessions_repository=repository,
        now_provider=lambda: created_at + timedelta(minutes=10),
    )

    with pytest.raises(SessionValidationError) as exc_info:
        service.update_session(db=object(), session_id="session-123", fields={"rating": 6})

    assert exc_info.value.code == "invalid_rating"


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

    assert created.name == "Late Night"
    assert [mood.name for mood in service.list_custom_moods(db=object())] == ["Late Night"]


def test_create_custom_mood_reuses_historical_session_casing(
    sessions_repository_factory,
    sessions_moods_repository_factory,
    build_sessions_service,
) -> None:
    sessions_repository = sessions_repository_factory()
    sessions_repository.sessions.append(
        Sessions(
            id="session-historical",
            release_id="release-123",
            rating=5,
            mood="LateNight",
            notes=None,
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side="A",
            created_at=datetime(2026, 4, 18, tzinfo=UTC),
        )
    )
    service = build_sessions_service(
        sessions_repository=sessions_repository,
        moods_repository=sessions_moods_repository_factory(),
    )

    created = service.create_custom_mood(db=object(), name="latenight")

    assert created.name == "LateNight"


def test_create_custom_mood_rejects_duplicate_names(
    sessions_moods_repository_factory,
    build_sessions_service,
) -> None:
    moods_repository = sessions_moods_repository_factory()
    service = build_sessions_service(moods_repository=moods_repository)
    service.create_custom_mood(db=object(), name="Late Night")

    with pytest.raises(SessionMoodAlreadyExistsError) as exc_info:
        service.create_custom_mood(db=object(), name="late night")

    assert exc_info.value.code == "duplicate_mood"


@pytest.mark.parametrize("name", ["Lo", "This Mood Name Is Too Long", "Dreamy!", "calm"])
def test_create_custom_mood_rejects_invalid_names(name: str, build_sessions_service) -> None:
    service = build_sessions_service()

    with pytest.raises(SessionValidationError) as exc_info:
        service.create_custom_mood(db=object(), name=name)

    assert exc_info.value.code == "invalid_mood"


def test_create_session_canonicalizes_mood_casing_from_history(
    sessions_repository_factory,
    build_sessions_service,
) -> None:
    repository = sessions_repository_factory()
    repository.sessions.append(
        Sessions(
            id="session-historical",
            release_id="release-123",
            rating=5,
            mood="LateNight",
            notes=None,
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side="A",
            created_at=datetime(2026, 4, 18, tzinfo=UTC),
        )
    )
    service = build_sessions_service(sessions_repository=repository)

    service.create_session(
        db=object(),
        release_id="release-123",
        rating=4,
        mood="latenight",
        notes=None,
        played_at="2026-03-15T19:21:00Z",
        side=None,
    )

    assert repository.created_payload is not None
    assert repository.created_payload["mood"] == "LateNight"


def test_delete_custom_mood_removes_saved_option(
    sessions_moods_repository_factory,
    build_sessions_service,
) -> None:
    moods_repository = sessions_moods_repository_factory()
    service = build_sessions_service(moods_repository=moods_repository)
    service.create_custom_mood(db=object(), name="Dubby")

    service.delete_custom_mood(db=object(), name="dubby")

    assert service.list_custom_moods(db=object()) == []
