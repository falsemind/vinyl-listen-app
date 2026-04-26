from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.pipelines.identification import IdentifyCandidate
from app.services.identify_service import IdentifyResult, IdentifyValidationError
from app.services.release_import_service import ReleaseImportResult
from app.services.sessions_service import CreateSessionResult


class StubIdentifyService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.result = IdentifyResult(
            candidates=(
                IdentifyCandidate(
                    discogs_release_id=555123,
                    release_id="release-123",
                    artist="Boards of Canada",
                    title="Music Has The Right To Children",
                    year=1998,
                    label="Warp Records",
                    catalog_number="WARPLP55",
                    barcode="5021603065515",
                    cover_image_url="https://img.discogs.com/cover.jpg",
                    match_source="local",
                    matched_on=("local_lookup", "barcode"),
                    confidence=0.733,
                ),
            )
        )
        self.error: IdentifyValidationError | None = None

    def identify(self, _db, *, image_bytes: bytes, filename: str, content_type: str) -> IdentifyResult:
        self.calls.append(
            {
                "size_bytes": len(image_bytes),
                "filename": filename,
                "content_type": content_type,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


@dataclass
class ReleaseStub:
    id: str
    discogs_release_id: int
    artist: str
    title: str
    year: int | None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    genres: list[str] | None
    styles: list[str] | None
    cover_image_url: str | None
    created_at: datetime
    updated_at: datetime


class StubReleaseImportService:
    def __init__(self) -> None:
        self.release = ReleaseStub(
            id="release-123",
            discogs_release_id=555123,
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
        self.import_result = ReleaseImportResult(release=self.release, created=True)
        self.import_error: Exception | None = None
        self.import_calls: list[tuple[int, bool]] = []
        self.lookup_calls: list[str] = []

    def import_release(self, _db, discogs_release_id: int, *, force_refresh: bool = False) -> ReleaseImportResult:
        self.import_calls.append((discogs_release_id, force_refresh))
        if self.import_error is not None:
            raise self.import_error
        return self.import_result

    def get_release(self, _db, release_id: str) -> ReleaseStub | None:
        self.lookup_calls.append(release_id)
        if release_id == self.release.id:
            return self.release
        return None


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


@pytest.fixture
def build_stub_identify_service() -> Callable[[], StubIdentifyService]:
    def _factory() -> StubIdentifyService:
        return StubIdentifyService()

    return _factory


@pytest.fixture
def build_stub_release_import_service() -> Callable[[], StubReleaseImportService]:
    def _factory() -> StubReleaseImportService:
        return StubReleaseImportService()

    return _factory


@pytest.fixture
def build_stub_sessions_service() -> Callable[[], StubSessionsService]:
    def _factory() -> StubSessionsService:
        return StubSessionsService()

    return _factory


@pytest.fixture
def override_identify_service() -> Callable[[StubIdentifyService], None]:
    def _override(service: StubIdentifyService) -> None:
        from app.api.routes.identify import get_identify_service
        from app.main import app

        app.dependency_overrides[get_identify_service] = lambda: service

    return _override


@pytest.fixture
def override_release_import_service() -> Callable[[StubReleaseImportService], None]:
    def _override(service: StubReleaseImportService) -> None:
        from app.api.routes.releases import get_release_import_service
        from app.main import app

        app.dependency_overrides[get_release_import_service] = lambda: service

    return _override


@pytest.fixture
def override_sessions_service() -> Callable[[StubSessionsService], None]:
    def _override(service: StubSessionsService) -> None:
        from app.api.routes.releases import get_sessions_service as get_release_sessions_service
        from app.api.routes.sessions import get_sessions_service
        from app.main import app

        app.dependency_overrides[get_sessions_service] = lambda: service
        app.dependency_overrides[get_release_sessions_service] = lambda: service

    return _override


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    from app.main import app

    app.dependency_overrides.clear()
