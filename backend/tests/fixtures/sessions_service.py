from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.releases import Releases
from app.models.sessions import Sessions
from app.services.sessions_service import SessionsService


class InMemorySessionsRepository:
    def __init__(self) -> None:
        self.created_session: Sessions | None = None
        self.created_payload: dict | None = None
        self.sessions: list[Sessions] = []

    def create(self, _db, **kwargs) -> Sessions:
        self.created_payload = kwargs
        session = Sessions(
            id="session-123",
            release_id=kwargs["release_id"],
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

    def get_by_release_id(self, _db, release_id: str, *, limit: int, offset: int) -> list[Sessions]:
        matching = [session for session in self.sessions if session.release_id == release_id]
        return matching[offset : offset + limit]


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
def build_sessions_service(
    build_release: Callable[[str, int], Releases],
) -> Callable[
    [InMemorySessionsRepository | None, list[Releases] | None, dict[int, dict] | None],
    SessionsService,
]:
    def _build_service(
        sessions_repository: InMemorySessionsRepository | None = None,
        releases: list[Releases] | None = None,
        payload_by_discogs_id: dict[int, dict] | None = None,
    ) -> SessionsService:
        return SessionsService(
            sessions_repository=sessions_repository or InMemorySessionsRepository(),
            releases_repository=InMemoryReleasesRepository(releases or [build_release()]),
            discogs_repository=StubDiscogsRepository(payload_by_discogs_id or {}),
        )

    return _build_service
