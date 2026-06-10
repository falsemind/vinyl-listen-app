from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.releases import Releases
from app.models.sessions import Sessions, SessionTracks
from app.models.sessions_moods import SessionsMoods
from app.services.session_groups_service import SessionGroupsService
from app.services.sessions_service import SessionsService


class InMemorySessionsRepository:
    def __init__(self) -> None:
        self.created_session: Sessions | None = None
        self.created_payload: dict | None = None
        self.updated_payload: dict | None = None
        self.sessions: list[Sessions] = []
        self.tracks_by_session_id: dict[str, list[SessionTracks]] = {}

    def create(self, _db, **kwargs) -> Sessions:
        self.created_payload = kwargs
        session = Sessions(
            id="session-123",
            release_id=kwargs["release_id"],
            session_group_id=kwargs.get("session_group_id"),
            rating=kwargs["rating"],
            mood=kwargs["mood"],
            notes=kwargs["notes"],
            played_at=kwargs["played_at"],
            vinyl_side=kwargs["vinyl_side"],
            created_at=datetime(2026, 4, 19, 8, 30, tzinfo=UTC),
        )
        self.created_session = session
        self.sessions.append(session)
        return session

    def get_by_id(self, _db, session_id: str) -> Sessions | None:
        for session in self.sessions:
            if session.id == session_id:
                return session
        return None

    def update(self, _db, session: Sessions, **kwargs) -> Sessions:
        self.updated_payload = kwargs
        session.rating = kwargs["rating"]
        session.mood = kwargs["mood"]
        session.notes = kwargs["notes"]
        session.vinyl_side = kwargs["vinyl_side"]
        return session

    def replace_tracks(self, _db, *, session_id: str, tracks: list[dict]) -> list[SessionTracks]:
        session_tracks = [
            SessionTracks(
                id=f"track-{index}",
                session_id=session_id,
                track_position=track["position"],
                track_title=track["title"],
                track_duration=track.get("duration"),
                track_sequence=track.get("sequence"),
                created_at=datetime(2026, 4, 19, 8, 30, tzinfo=UTC),
            )
            for index, track in enumerate(tracks, start=1)
        ]
        self.tracks_by_session_id[session_id] = session_tracks
        return session_tracks

    def get_tracks_by_session_id(self, _db, session_id: str) -> list[SessionTracks]:
        return self.tracks_by_session_id.get(session_id, [])

    def get_tracks_by_session_ids(self, _db, session_ids: list[str]) -> dict[str, list[SessionTracks]]:
        return {session_id: self.tracks_by_session_id.get(session_id, []) for session_id in session_ids}

    def get_by_release_id(self, _db, release_id: str, *, limit: int, offset: int) -> list[Sessions]:
        matching = [session for session in self.sessions if session.release_id == release_id]
        return matching[offset : offset + limit]

    def get_mood_by_name(self, _db, name: str) -> str | None:
        for session in sorted(self.sessions, key=lambda item: item.created_at):
            if session.mood is not None and session.mood.lower() == name.lower():
                return session.mood
        return None


class InMemoryReleasesRepository:
    def __init__(self, releases: list[Releases]) -> None:
        self.releases = {release.id: release for release in releases}

    def get_by_id(self, _db, release_id: str) -> Releases | None:
        return self.releases.get(release_id)


class StubDiscogsRepository:
    def __init__(self, payload_by_discogs_id: dict[int, dict]) -> None:
        self.payload_by_discogs_id = payload_by_discogs_id

    def get_by_discogs_release_id(self, _db, discogs_release_id: int):
        payload = self.payload_by_discogs_id.get(discogs_release_id)
        if payload is None:
            return None
        return SimpleNamespace(raw_discogs_json=payload)


class InMemorySessionsMoodsRepository:
    def __init__(self) -> None:
        self.moods: list[SessionsMoods] = []

    def get_custom(self, _db) -> list[SessionsMoods]:
        return sorted([mood for mood in self.moods if mood.is_custom], key=lambda mood: mood.name)

    def get_by_name(self, _db, name: str) -> SessionsMoods | None:
        for mood in self.moods:
            if mood.name.lower() == name.lower():
                return mood
        return None

    def create_custom(self, _db, name: str) -> SessionsMoods:
        mood = SessionsMoods(name=name, is_custom=True)
        self.moods.append(mood)
        return mood

    def delete_custom(self, _db, name: str) -> bool:
        mood = self.get_by_name(_db, name)
        if mood is None or not mood.is_custom:
            return False
        self.moods.remove(mood)
        return True


@pytest.fixture
def build_release() -> Callable[[str, int], Releases]:
    def _build_release(release_id: str = "release-123", discogs_release_id: int = 555123) -> Releases:
        return Releases(
            id=release_id,
            discogs_release_id=discogs_release_id,
            artist="Boards of Canada",
            title="Music Has The Right To Children",
            year=1998,
            label="Warp Records",
            catalog_number="WARPLP55",
            barcode="5021603065515",
            genres=["Electronic"],
            styles=["IDM"],
            cover_image_url="https://img.discogs.com/cover.jpg",
            created_at=datetime(2026, 4, 19, tzinfo=UTC),
            updated_at=datetime(2026, 4, 19, tzinfo=UTC),
        )

    return _build_release


@pytest.fixture
def sessions_repository_factory() -> Callable[[], InMemorySessionsRepository]:
    def _factory() -> InMemorySessionsRepository:
        return InMemorySessionsRepository()

    return _factory


@pytest.fixture
def sessions_moods_repository_factory() -> Callable[[], InMemorySessionsMoodsRepository]:
    def _factory() -> InMemorySessionsMoodsRepository:
        return InMemorySessionsMoodsRepository()

    return _factory


@pytest.fixture
def build_sessions_service(
    build_release: Callable[[str, int], Releases],
) -> Callable[
    [
        InMemorySessionsRepository | None,
        list[Releases] | None,
        dict[int, dict] | None,
        InMemorySessionsMoodsRepository | None,
        SessionGroupsService | None,
        Callable[[], datetime] | None,
    ],
    SessionsService,
]:
    def _build_service(
        sessions_repository: InMemorySessionsRepository | None = None,
        releases: list[Releases] | None = None,
        payload_by_discogs_id: dict[int, dict] | None = None,
        moods_repository: InMemorySessionsMoodsRepository | None = None,
        session_groups_service: SessionGroupsService | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> SessionsService:
        return SessionsService(
            sessions_repository=sessions_repository or InMemorySessionsRepository(),
            releases_repository=InMemoryReleasesRepository(releases or [build_release()]),
            discogs_repository=StubDiscogsRepository(payload_by_discogs_id or {}),
            moods_repository=moods_repository or InMemorySessionsMoodsRepository(),
            session_groups_service=session_groups_service,
            now_provider=now_provider,
        )

    return _build_service
