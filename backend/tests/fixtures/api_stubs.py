from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.pipelines.identification import IdentifyCandidate
from app.schemas.identify import IdentifyJobStatus, IdentifyJobStatusResponse
from app.services.identify_job_service import IdentifyCapacityExceededError
from app.services.identify_service import IdentifyResult, IdentifyValidationError
from app.services.release_import_service import ReleaseImportResult
from app.services.release_mapper import (
    ReleaseArtistData,
    ReleaseSideOptionData,
    ReleaseTrackArtistData,
    ReleaseTrackCreditData,
    ReleaseTrackData,
)
from app.services.sessions_service import (
    CreateSessionResult,
    HomeSummary,
    RecordFlowInsights,
    RecordFlowMoodTransition,
    RecordFlowReleaseSummary,
    SessionReleaseSummary,
    TopReleaseSummary,
)


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
                    format="Vinyl, LP",
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


class StubIdentifyJobService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.process_calls: list[dict[str, object]] = []
        timestamp = datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC)
        self.response = IdentifyJobStatusResponse(
            job_id="job-123",
            status=IdentifyJobStatus.UPLOAD_RECEIVED,
            message="Image upload received",
            created_at=timestamp,
            updated_at=timestamp,
            result=None,
            error=None,
        )
        self.create_error: Exception | None = None
        self.get_error: Exception | None = None
        self.cancel_error: Exception | None = None
        self.cancel_response: IdentifyJobStatusResponse | None = None
        self.cancel_calls: list[str] = []

    def create_job(
        self,
        _db,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        client_key: str = "unknown",
    ) -> IdentifyJobStatusResponse:
        _ = client_key
        self.calls.append(
            {
                "size_bytes": len(image_bytes),
                "filename": filename,
                "content_type": content_type,
            }
        )
        if self.create_error is not None:
            raise self.create_error
        return self.response

    def acquire_sync_identify_slot(self):
        if isinstance(self.create_error, IdentifyCapacityExceededError):
            raise self.create_error

        class _Ticket:
            @staticmethod
            def release() -> None:
                return None

        return _Ticket()

    def process_job(self, job_id: str, *, image_bytes: bytes, filename: str, content_type: str) -> None:
        self.process_calls.append(
            {
                "job_id": job_id,
                "size_bytes": len(image_bytes),
                "filename": filename,
                "content_type": content_type,
            }
        )

    def get_job(self, _db, job_id: str) -> IdentifyJobStatusResponse:
        if self.get_error is not None:
            raise self.get_error
        return self.response.model_copy(update={"job_id": job_id})

    def cancel_job(self, _db, job_id: str) -> IdentifyJobStatusResponse:
        self.cancel_calls.append(job_id)
        if self.cancel_error is not None:
            raise self.cancel_error
        response = self.cancel_response or self.response.model_copy(update={"cancel_requested": True})
        return response.model_copy(update={"job_id": job_id})


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
    format: str | None = None
    thumbnail_url: str | None = None
    in_collection: bool = False
    collection_added_at: datetime | None = None
    collection_removed_at: datetime | None = None
    last_discogs_sync_at: datetime | None = None
    discogs_instance_id: int | None = None
    is_favorite: bool = False


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
        self.collection_import_error: Exception | None = None
        self.collection_import_calls: list[tuple[int, bool]] = []
        self.client_import_error: Exception | None = None
        self.client_import_calls: list[dict] = []
        self.refresh_calls: list[str] = []
        self.lookup_calls: list[str] = []
        self.favorite_calls: list[tuple[str, bool]] = []
        self.deactivate_calls: list[str] = []
        self.reactivate_calls: list[str] = []
        self.has_full_discogs_info_value = True
        self.available_sides = ["A", "AA"]
        self.available_side_options = [
            ReleaseSideOptionData(value="A", label="Side A", side="A"),
            ReleaseSideOptionData(value="AA", label="Side AA", side="AA"),
        ]
        self.tracklist = [
            ReleaseTrackData(position="A1", title="Wildlife Analysis", duration="1:17"),
            ReleaseTrackData(
                position="A2",
                title="An Eagle In Your Mind",
                artists=[
                    ReleaseTrackArtistData(name="Boards of Canada", join="&", discogs_artist_id=194),
                    ReleaseTrackArtistData(name="Plaid", discogs_artist_id=2470),
                ],
                extra_artists=[ReleaseTrackCreditData(name="Plaid", role="Remix")],
            ),
        ]
        self.artists = [
            ReleaseArtistData(name="Boards of Canada", discogs_artist_id=194),
        ]

    def import_release(self, _db, discogs_release_id: int, *, force_refresh: bool = False) -> ReleaseImportResult:
        self.import_calls.append((discogs_release_id, force_refresh))
        if self.import_error is not None:
            raise self.import_error
        return self.import_result

    def import_release_to_collection(
        self,
        _db,
        discogs_release_id: int,
        *,
        force_refresh: bool = False,
    ) -> ReleaseImportResult:
        self.collection_import_calls.append((discogs_release_id, force_refresh))
        if self.collection_import_error is not None:
            raise self.collection_import_error
        self.release.in_collection = True
        self.release.collection_added_at = datetime(2026, 6, 16, tzinfo=UTC)
        self.release.collection_removed_at = None
        return self.import_result

    def import_client_discogs_release(self, _db, raw_payload: dict) -> ReleaseImportResult:
        self.client_import_calls.append(raw_payload)
        if self.client_import_error is not None:
            raise self.client_import_error
        return self.import_result

    def get_release(self, _db, release_id: str) -> ReleaseStub | None:
        self.lookup_calls.append(release_id)
        if release_id == self.release.id:
            return self.release
        return None

    def refresh_release(self, db, release_id: str) -> ReleaseImportResult | None:
        self.refresh_calls.append(release_id)
        release = self.get_release(db, release_id)
        if release is None:
            return None
        return self.import_release(db, release.discogs_release_id, force_refresh=True)

    def has_full_discogs_info(self, _db, _discogs_release_id: int) -> bool:
        return self.has_full_discogs_info_value

    def get_available_sides(self, _db, discogs_release_id: int) -> list[str]:
        if discogs_release_id == self.release.discogs_release_id:
            return self.available_sides
        return []

    def get_available_side_options(self, _db, discogs_release_id: int) -> list[ReleaseSideOptionData]:
        if discogs_release_id == self.release.discogs_release_id:
            return self.available_side_options
        return []

    def get_tracklist(self, _db, discogs_release_id: int) -> list[ReleaseTrackData]:
        if discogs_release_id == self.release.discogs_release_id:
            return self.tracklist
        return []

    def get_artists(self, _db, discogs_release_id: int) -> list[ReleaseArtistData]:
        if discogs_release_id == self.release.discogs_release_id:
            return self.artists
        return []

    def set_favorite(self, _db, release: ReleaseStub, *, is_favorite: bool) -> ReleaseStub:
        self.favorite_calls.append((release.id, is_favorite))
        release.is_favorite = is_favorite
        return release

    def deactivate_collection_membership(self, _db, release: ReleaseStub, *, removed_at: datetime) -> ReleaseStub:
        self.deactivate_calls.append(release.id)
        release.in_collection = False
        release.collection_removed_at = removed_at
        return release

    def reactivate_collection_membership(self, _db, release: ReleaseStub, *, added_at: datetime) -> ReleaseStub:
        self.reactivate_calls.append(release.id)
        release.in_collection = True
        release.collection_added_at = added_at
        release.collection_removed_at = None
        return release


class StubDiscogsSearchService:
    def __init__(self) -> None:
        self.payload = {
            "results": [
                {
                    "id": 555123,
                    "title": "Boards of Canada - Music Has The Right To Children",
                    "year": 1998,
                    "label": ["Warp Records"],
                    "catno": "WARPLP55",
                    "format": ["Vinyl", "LP"],
                    "thumb": "https://img.discogs.com/thumb.jpg",
                }
            ]
        }
        self.error: Exception | None = None
        self.calls: list[dict[str, object]] = []

    def search_releases(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.payload


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
    session_group_id: str | None = None


@dataclass
class SessionGroupStub:
    id: str = "group-123"
    title: str | None = "Late night stack"
    status: str = "active"
    style_focus: str = "mixed"
    mood_direction: str = "steady_mood"
    session_type: str = "casual_listening"
    notes: str | None = None
    started_at: datetime = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)
    ended_at: datetime | None = None
    created_at: datetime = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)
    updated_at: datetime = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)


class StubSessionGroupsService:
    def __init__(self) -> None:
        self.group = SessionGroupStub()
        self.active_group: SessionGroupStub | None = self.group
        self.start_error: Exception | None = None
        self.get_error: Exception | None = None
        self.finish_error: Exception | None = None
        self.start_calls: list[dict] = []
        self.get_calls: list[str] = []
        self.get_by_ids_calls: list[list[str]] = []
        self.update_calls: list[tuple[str, dict]] = []
        self.finish_calls: list[tuple[str, str | None, str | None, str | None, str | None, str | None]] = []

    def start_session_group(
        self,
        _db,
        *,
        title: str | None,
        started_at: str | None = None,
        style_focus: str | None = None,
        mood_direction: str | None = None,
        session_type: str | None = None,
        notes: str | None = None,
    ) -> SessionGroupStub:
        self.start_calls.append(
            {
                "title": title,
                "started_at": started_at,
                "style_focus": style_focus,
                "mood_direction": mood_direction,
                "session_type": session_type,
                "notes": notes,
            }
        )
        if self.start_error is not None:
            raise self.start_error
        if style_focus is not None:
            self.group.style_focus = style_focus
        if mood_direction is not None:
            self.group.mood_direction = mood_direction
        if session_type is not None:
            self.group.session_type = session_type
        if notes is not None:
            self.group.notes = notes
        return self.group

    def get_active_session_group(self, _db) -> SessionGroupStub | None:
        return self.active_group

    def get_session_group(self, _db, session_group_id: str) -> SessionGroupStub:
        self.get_calls.append(session_group_id)
        if self.get_error is not None:
            raise self.get_error
        return self.group

    def get_session_groups_by_ids(self, _db, session_group_ids: list[str]) -> list[SessionGroupStub]:
        self.get_by_ids_calls.append(session_group_ids)
        if self.get_error is not None:
            raise self.get_error
        return [self.group] if self.group.id in session_group_ids else []

    def update_session_group(self, _db, session_group_id: str, *, fields: dict) -> SessionGroupStub:
        self.update_calls.append((session_group_id, fields))
        if self.get_error is not None:
            raise self.get_error
        for field, value in fields.items():
            setattr(self.group, field, value)
        return self.group

    def finish_session_group(
        self,
        _db,
        session_group_id: str,
        *,
        ended_at: str | None = None,
        style_focus: str | None = None,
        mood_direction: str | None = None,
        session_type: str | None = None,
        notes: str | None = None,
    ) -> SessionGroupStub:
        self.finish_calls.append((session_group_id, ended_at, style_focus, mood_direction, session_type, notes))
        if self.finish_error is not None:
            raise self.finish_error
        if style_focus is not None:
            self.group.style_focus = style_focus
        if mood_direction is not None:
            self.group.mood_direction = mood_direction
        if session_type is not None:
            self.group.session_type = session_type
        if notes is not None:
            self.group.notes = notes
        self.group.status = "completed"
        self.group.ended_at = datetime(2026, 4, 19, 9, 0, tzinfo=UTC)
        self.group.updated_at = self.group.ended_at
        return self.group

    def can_edit_session_group(self, _session_group: SessionGroupStub) -> bool:
        return True

    def editable_until(self, session_group: SessionGroupStub) -> datetime | None:
        if session_group.ended_at is None:
            return None
        return session_group.ended_at.replace(minute=session_group.ended_at.minute + 15)


class StubSessionsService:
    def __init__(self) -> None:
        self.create_error: Exception | None = None
        self.get_error: Exception | None = None
        self.update_error: Exception | None = None
        self.list_error: Exception | None = None
        self.summary_error: Exception | None = None
        self.mood_error: Exception | None = None
        self.create_calls: list[dict] = []
        self.get_calls: list[str] = []
        self.update_calls: list[tuple[str, dict]] = []
        self.list_calls: list[tuple[str, int, int]] = []
        self.summary_calls: list[tuple[int, int]] = []
        self.flow_calls: list[tuple[str, int, str]] = []
        self.create_mood_calls: list[str] = []
        self.delete_mood_calls: list[str] = []
        self.custom_moods = [
            SimpleNamespace(name="Dubby", is_custom=True),
            SimpleNamespace(name="Late Night", is_custom=True),
        ]
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
        self.tracks_by_session_id = {
            "session-123": [
                SimpleNamespace(
                    track_position="A1",
                    track_artist="Boards of Canada",
                    track_title="Wildlife Analysis",
                    track_duration="1:17",
                    track_sequence=1,
                )
            ]
        }
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
        self.before_release = ReleaseStub(
            id="release-before",
            discogs_release_id=555124,
            artist="Aphex Twin",
            title="Selected Ambient Works 85-92",
            year=1992,
            label="Apollo",
            catalog_number="AMB3922LP",
            barcode=None,
            genres=["Electronic"],
            styles=["Ambient"],
            cover_image_url="https://img.discogs.com/before.jpg",
            created_at=datetime(2026, 4, 19, tzinfo=UTC),
            updated_at=datetime(2026, 4, 19, tzinfo=UTC),
        )
        self.after_release = ReleaseStub(
            id="release-after",
            discogs_release_id=555125,
            artist="Basic Channel",
            title="Quadrant Dub",
            year=1994,
            label="Basic Channel",
            catalog_number="BC-06",
            barcode=None,
            genres=["Electronic"],
            styles=["Dub Techno"],
            cover_image_url="https://img.discogs.com/after.jpg",
            created_at=datetime(2026, 4, 19, tzinfo=UTC),
            updated_at=datetime(2026, 4, 19, tzinfo=UTC),
        )
        self.flow_insights = RecordFlowInsights(
            release_id="release-123",
            before=[RecordFlowReleaseSummary(release=self.before_release, count=2)],
            after=[RecordFlowReleaseSummary(release=self.after_release, count=1)],
            mood_transitions=[
                RecordFlowMoodTransition(
                    previous_mood="Calm",
                    current_mood="Focused",
                    next_mood="Energetic",
                    count=1,
                )
            ],
            sample_size=2,
            confidence="low",
        )

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

    def update_session(self, _db, *, session_id: str, fields: dict) -> SessionStub:
        self.update_calls.append((session_id, fields))
        if self.update_error is not None:
            raise self.update_error
        if "rating" in fields:
            self.session.rating = fields["rating"]
        if "mood" in fields:
            self.session.mood = fields["mood"]
        if "notes" in fields:
            self.session.notes = fields["notes"]
        if "side" in fields:
            self.session.vinyl_side = fields["side"]
        if "track_positions" in fields:
            self.tracks_by_session_id[self.session.id] = [
                SimpleNamespace(
                    track_position=position,
                    track_artist=None,
                    track_title=f"Track {position}",
                    track_duration=None,
                    track_sequence=index,
                )
                for index, position in enumerate(fields["track_positions"] or [], start=1)
            ]
        return self.session

    def can_edit_session(self, _session: SessionStub) -> bool:
        return True

    def editable_until(self, session: SessionStub) -> datetime:
        return session.created_at.replace(minute=session.created_at.minute + 15)

    def get_session_tracks(self, _db, session_id: str):
        return self.tracks_by_session_id.get(session_id, [])

    def get_tracks_by_session_ids(self, _db, session_ids: list[str]):
        return {session_id: self.tracks_by_session_id.get(session_id, []) for session_id in session_ids}

    def get_sessions_by_release(self, _db, release_id: str, *, limit: int, offset: int) -> list[SessionStub]:
        self.list_calls.append((release_id, limit, offset))
        if self.list_error is not None:
            raise self.list_error
        return self.release_sessions[offset : offset + limit]

    def get_home_summary(self, _db, *, recent_limit: int, top_limit: int) -> HomeSummary:
        self.summary_calls.append((recent_limit, top_limit))
        if self.summary_error is not None:
            raise self.summary_error
        return HomeSummary(
            recent_sessions=[
                SessionReleaseSummary(session=self.release_sessions[0], release=self.release),
            ],
            total_sessions=2,
            records_this_month=1,
            top_records=[
                TopReleaseSummary(release=self.release, plays=2, average_rating=4.5),
            ],
        )

    def get_record_flow_insights(
        self,
        _db,
        release_id: str,
        *,
        limit: int = 5,
        period: str = "3m",
    ) -> RecordFlowInsights:
        self.flow_calls.append((release_id, limit, period))
        if self.list_error is not None:
            raise self.list_error
        return self.flow_insights

    def list_custom_moods(self, _db):
        if self.mood_error is not None:
            raise self.mood_error
        return self.custom_moods

    def create_custom_mood(self, _db, name: str):
        self.create_mood_calls.append(name)
        if self.mood_error is not None:
            raise self.mood_error
        mood = SimpleNamespace(name=name.strip(), is_custom=True)
        self.custom_moods.append(mood)
        return mood

    def delete_custom_mood(self, _db, name: str) -> None:
        self.delete_mood_calls.append(name)
        if self.mood_error is not None:
            raise self.mood_error
        self.custom_moods = [mood for mood in self.custom_moods if mood.name != name]


@pytest.fixture
def build_stub_identify_service() -> Callable[[], StubIdentifyService]:
    def _factory() -> StubIdentifyService:
        return StubIdentifyService()

    return _factory


@pytest.fixture
def build_stub_identify_job_service() -> Callable[[], StubIdentifyJobService]:
    def _factory() -> StubIdentifyJobService:
        return StubIdentifyJobService()

    return _factory


@pytest.fixture
def build_stub_release_import_service() -> Callable[[], StubReleaseImportService]:
    def _factory() -> StubReleaseImportService:
        return StubReleaseImportService()

    return _factory


@pytest.fixture
def build_stub_discogs_search_service() -> Callable[[], StubDiscogsSearchService]:
    def _factory() -> StubDiscogsSearchService:
        return StubDiscogsSearchService()

    return _factory


@pytest.fixture
def build_stub_sessions_service() -> Callable[[], StubSessionsService]:
    def _factory() -> StubSessionsService:
        return StubSessionsService()

    return _factory


@pytest.fixture
def build_stub_session_groups_service() -> Callable[[], StubSessionGroupsService]:
    def _factory() -> StubSessionGroupsService:
        return StubSessionGroupsService()

    return _factory


@pytest.fixture
def override_identify_service() -> Callable[[StubIdentifyService], None]:
    def _override(service: StubIdentifyService) -> None:
        from app.api.routes.identify import get_identify_service
        from app.main import app

        app.dependency_overrides[get_identify_service] = lambda: service

    return _override


@pytest.fixture
def override_identify_job_service() -> Callable[[StubIdentifyJobService], None]:
    def _override(service: StubIdentifyJobService) -> None:
        from app.api.routes.identify import get_identify_job_service
        from app.main import app

        app.dependency_overrides[get_identify_job_service] = lambda: service

    return _override


@pytest.fixture
def override_release_import_service() -> Callable[[StubReleaseImportService], None]:
    def _override(service: StubReleaseImportService) -> None:
        from app.api.routes.releases import get_release_import_service
        from app.main import app

        app.dependency_overrides[get_release_import_service] = lambda: service

    return _override


@pytest.fixture
def override_discogs_service() -> Callable[[StubDiscogsSearchService], None]:
    def _override(service: StubDiscogsSearchService) -> None:
        from app.api.routes.releases import get_discogs_service
        from app.main import app

        app.dependency_overrides[get_discogs_service] = lambda: service

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


@pytest.fixture
def override_session_groups_service() -> Callable[[StubSessionGroupsService], None]:
    def _override(service: StubSessionGroupsService) -> None:
        from app.api.routes.sessions import get_session_groups_service
        from app.main import app

        app.dependency_overrides[get_session_groups_service] = lambda: service

    return _override


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    from app.main import app

    app.dependency_overrides.clear()
