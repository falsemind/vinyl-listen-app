import logging
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.releases import Releases
from app.models.sessions import Sessions, SessionTracks
from app.models.sessions_moods import SessionsMoods
from app.repositories.discogs_release_repository import DiscogsReleaseRepository
from app.repositories.releases_repository import ReleasesRepository
from app.repositories.sessions_moods_repository import SessionsMoodsRepository
from app.repositories.sessions_repository import SessionsRepository
from app.services.release_mapper import (
    ReleaseTrackArtistData,
    ReleaseTrackData,
    extract_release_side_options,
    extract_release_tracklist,
)
from app.services.session_groups_service import SessionGroupsService

logger = logging.getLogger(__name__)

CUSTOM_MOOD_MIN_LENGTH = 3
CUSTOM_MOOD_MAX_LENGTH = 20
SESSION_EDIT_WINDOW = timedelta(minutes=15)
FLOW_INSIGHTS_STANDALONE_GAP = timedelta(hours=1)
FLOW_INSIGHTS_PERIOD_WINDOWS = {
    "3m": timedelta(days=90),
    "6m": timedelta(days=180),
    "1y": timedelta(days=365),
    "all": None,
}
BUILT_IN_SESSION_MOODS = {
    "energetic": "Energetic",
    "calm": "Calm",
    "melancholic": "Melancholic",
    "nostalgic": "Nostalgic",
    "focused": "Focused",
    "background": "Background",
}


class SessionsServiceError(Exception):
    """Base error for listening-session service failures."""


class SessionValidationError(SessionsServiceError):
    """Raised when session input fails business-rule validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SessionMoodAlreadyExistsError(SessionsServiceError):
    """Raised when a custom mood name already exists."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Mood '{name}' already exists.")
        self.code = "duplicate_mood"
        self.message = "Mood already exists."


class SessionNotFoundError(SessionsServiceError):
    """Raised when a session cannot be found."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' was not found.")
        self.session_id = session_id


class SessionEditWindowExpiredError(SessionsServiceError):
    """Raised when a session is too old to edit."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' can no longer be edited.")
        self.code = "session_edit_window_expired"
        self.message = "Session can only be edited for 15 minutes after it is created."
        self.session_id = session_id


class ReleaseNotFoundError(SessionsServiceError):
    """Raised when a release cannot be found."""

    def __init__(self, release_id: str) -> None:
        super().__init__(f"Release '{release_id}' was not found.")
        self.release_id = release_id


@dataclass(frozen=True)
class SessionTrackSelection:
    position: str
    artist: str | None
    title: str
    duration: str | None
    sequence: int

    def as_repository_payload(self) -> dict[str, object]:
        return {
            "position": self.position,
            "artist": self.artist,
            "title": self.title,
            "duration": self.duration,
            "sequence": self.sequence,
        }


@dataclass(frozen=True)
class SessionTrackSnapshot:
    track_position: str
    track_artist: str | None
    track_title: str
    track_duration: str | None
    track_sequence: int | None


@dataclass(frozen=True)
class CreateSessionData:
    release_id: str
    session_group_id: str | None
    rating: int | None
    mood: str | None
    notes: str | None
    played_at: datetime
    side: str | None
    tracks: list[SessionTrackSelection]


@dataclass(frozen=True)
class UpdateSessionData:
    rating: int | None
    mood: str | None
    notes: str | None
    side: str | None
    tracks: list[SessionTrackSelection] | None


@dataclass(frozen=True)
class CreateSessionResult:
    session_id: str
    timestamp: datetime
    session_group_id: str | None = None
    status: str = "success"


@dataclass(frozen=True)
class SessionReleaseSummary:
    session: Sessions
    release: Releases


@dataclass(frozen=True)
class TopReleaseSummary:
    release: Releases
    plays: int
    average_rating: float | None


@dataclass(frozen=True)
class HomeSummary:
    recent_sessions: list[SessionReleaseSummary]
    total_sessions: int
    records_this_month: int
    top_records: list[TopReleaseSummary]


@dataclass(frozen=True)
class RecordFlowReleaseSummary:
    release: Releases
    count: int


@dataclass(frozen=True)
class RecordFlowMoodTransition:
    previous_mood: str | None
    current_mood: str | None
    next_mood: str | None
    count: int


@dataclass(frozen=True)
class RecordFlowInsights:
    release_id: str
    before: list[RecordFlowReleaseSummary]
    after: list[RecordFlowReleaseSummary]
    mood_transitions: list[RecordFlowMoodTransition]
    sample_size: int
    confidence: str


@dataclass
class _RecordFlowBlock:
    release: Releases
    moods: list[str | None]

    @property
    def primary_mood(self) -> str | None:
        return next((mood for mood in self.moods if mood), None)


@dataclass(frozen=True)
class _RecordFlowItem:
    session: Sessions
    release: Releases


class SessionsService:
    def __init__(
        self,
        sessions_repository: SessionsRepository | None = None,
        releases_repository: ReleasesRepository | None = None,
        discogs_repository: DiscogsReleaseRepository | None = None,
        moods_repository: SessionsMoodsRepository | None = None,
        session_groups_service: SessionGroupsService | None = None,
        now_provider: Any | None = None,
        max_page_limit: int | None = None,
    ) -> None:
        self._sessions_repository = sessions_repository or SessionsRepository()
        self._releases_repository = releases_repository or ReleasesRepository()
        self._discogs_repository = discogs_repository or DiscogsReleaseRepository()
        self._moods_repository = moods_repository or SessionsMoodsRepository()
        self._session_groups_service = session_groups_service or SessionGroupsService()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._max_page_limit = max_page_limit or settings.max_page_limit

    def create_session(
        self,
        db: Session,
        *,
        release_id: str,
        rating: int | None,
        mood: str | None,
        notes: str | None,
        played_at: str,
        side: str | None,
        track_positions: list[str] | None = None,
        session_group_id: str | None = None,
    ) -> CreateSessionResult:
        logger.info("Creating session release_id=%s played_at=%s", release_id, played_at)
        validated = self._validate_create_input(
            db,
            release_id=release_id,
            rating=rating,
            mood=mood,
            notes=notes,
            played_at=played_at,
            side=side,
            track_positions=track_positions,
            session_group_id=session_group_id,
        )
        session = self._sessions_repository.create(
            db,
            release_id=validated.release_id,
            session_group_id=validated.session_group_id,
            rating=validated.rating,
            mood=validated.mood,
            notes=validated.notes,
            played_at=validated.played_at,
            vinyl_side=validated.side,
        )
        if validated.tracks:
            self._sessions_repository.replace_tracks(
                db,
                session_id=session.id,
                tracks=[track.as_repository_payload() for track in validated.tracks],
            )
        logger.info("Created session session_id=%s release_id=%s", session.id, release_id)
        return CreateSessionResult(
            session_id=session.id,
            timestamp=session.created_at,
            session_group_id=session.session_group_id,
        )

    def get_session(self, db: Session, session_id: str) -> Sessions:
        logger.info("Loading session session_id=%s", session_id)
        session = self._sessions_repository.get_by_id(db, session_id)
        if session is None:
            logger.info("Session not found session_id=%s", session_id)
            raise SessionNotFoundError(session_id)
        return session

    def update_session(
        self,
        db: Session,
        *,
        session_id: str,
        fields: dict[str, Any],
    ) -> Sessions:
        logger.info("Updating session session_id=%s fields=%s", session_id, sorted(fields))
        if not fields:
            raise SessionValidationError("invalid_request", "At least one editable field is required.")

        allowed_fields = {"rating", "mood", "notes", "side", "track_positions"}
        unknown_fields = set(fields) - allowed_fields
        if unknown_fields:
            raise SessionValidationError(
                "invalid_request",
                "Only side, track_positions, rating, mood, and notes can be edited.",
            )

        session = self._sessions_repository.get_by_id(db, session_id)
        if session is None:
            logger.info("Session not found during update session_id=%s", session_id)
            raise SessionNotFoundError(session_id)
        if not self.can_edit_session(session):
            logger.info("Rejecting session update expired_edit_window session_id=%s", session_id)
            raise SessionEditWindowExpiredError(session_id)

        validated = self._validate_update_input(db, session=session, fields=fields)
        updated_session = self._sessions_repository.update(
            db,
            session,
            rating=validated.rating,
            mood=validated.mood,
            notes=validated.notes,
            vinyl_side=validated.side,
        )
        if validated.tracks is not None:
            self._sessions_repository.replace_tracks(
                db,
                session_id=updated_session.id,
                tracks=[track.as_repository_payload() for track in validated.tracks],
            )
        return updated_session

    def can_edit_session(self, session: Sessions) -> bool:
        return self._current_time() <= self.editable_until(session)

    def editable_until(self, session: Sessions) -> datetime:
        return self._as_aware_utc(session.created_at) + SESSION_EDIT_WINDOW

    def get_sessions_by_release(
        self,
        db: Session,
        release_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[Sessions]:
        if limit <= 0:
            logger.info("Rejecting sessions lookup release_id=%s invalid_limit=%s", release_id, limit)
            raise SessionValidationError("invalid_pagination", "limit must be greater than 0.")
        if offset < 0:
            logger.info("Rejecting sessions lookup release_id=%s invalid_offset=%s", release_id, offset)
            raise SessionValidationError("invalid_pagination", "offset cannot be negative.")

        release = self._releases_repository.get_by_id(db, release_id)
        if release is None:
            logger.info("Release not found during sessions lookup release_id=%s", release_id)
            raise ReleaseNotFoundError(release_id)

        logger.info("Loading sessions release_id=%s limit=%s offset=%s", release_id, limit, offset)
        return self._sessions_repository.get_by_release_id(
            db,
            release_id,
            limit=limit,
            offset=offset,
        )

    def get_session_tracks(self, db: Session, session_id: str) -> list[SessionTracks]:
        return self._sessions_repository.get_tracks_by_session_id(db, session_id)

    def get_tracks_by_session_ids(self, db: Session, session_ids: list[str]) -> dict[str, list[SessionTracks]]:
        return self._sessions_repository.get_tracks_by_session_ids(db, session_ids)

    def get_session_tracks_for_response(self, db: Session, session: Sessions) -> list[SessionTrackSnapshot]:
        tracks = self._sessions_repository.get_tracks_by_session_id(db, session.id)
        release = self._releases_repository.get_by_id(db, session.release_id)
        return self._enrich_track_artists(db, release, tracks)

    def get_tracks_by_session_ids_for_release_id(
        self,
        db: Session,
        *,
        release_id: str,
        session_ids: list[str],
    ) -> dict[str, list[SessionTrackSnapshot]]:
        tracks_by_session_id = self._sessions_repository.get_tracks_by_session_ids(db, session_ids)
        release = self._releases_repository.get_by_id(db, release_id)
        return {
            session_id: self._enrich_track_artists(db, release, tracks)
            for session_id, tracks in tracks_by_session_id.items()
        }

    def get_tracks_by_session_ids_for_releases(
        self,
        db: Session,
        session_releases: list[tuple[str, Releases]],
    ) -> dict[str, list[SessionTrackSnapshot]]:
        session_ids = [session_id for session_id, _release in session_releases]
        tracks_by_session_id = self._sessions_repository.get_tracks_by_session_ids(db, session_ids)
        release_by_session_id = dict(session_releases)
        lookup_cache: dict[int, tuple[dict[tuple[str, str], str], dict[str, str]]] = {}
        return {
            session_id: self._enrich_track_artists(
                db,
                release_by_session_id.get(session_id),
                tracks,
                lookup_cache=lookup_cache,
            )
            for session_id, tracks in tracks_by_session_id.items()
        }

    def get_record_flow_insights(
        self,
        db: Session,
        release_id: str,
        *,
        limit: int = 5,
        period: str = "3m",
    ) -> RecordFlowInsights:
        if limit <= 0 or limit > 10:
            raise SessionValidationError("invalid_limit", "limit must be between 1 and 10.")
        since = self._flow_insights_since(period)

        release = self._releases_repository.get_by_id(db, release_id)
        if release is None:
            logger.info("Release not found during flow insights lookup release_id=%s", release_id)
            raise ReleaseNotFoundError(release_id)

        sessions = self._sessions_repository.get_flow_insight_sessions(db, since=since)
        releases = {
            release.id: release
            for release in self._releases_repository.get_by_ids(
                db,
                list({session.release_id for session in sessions}),
            )
        }
        items = [
            _RecordFlowItem(session=session, release=releases[session.release_id])
            for session in sessions
            if session.release_id in releases
        ]
        sequences = self._flow_sequences(items)

        before_counts: Counter[str] = Counter()
        after_counts: Counter[str] = Counter()
        mood_counts: Counter[tuple[str | None, str | None, str | None]] = Counter()
        release_by_id = {item.release.id: item.release for item in items}
        sample_size = 0

        for sequence in sequences:
            for index, block in enumerate(sequence):
                if block.release.id != release_id:
                    continue

                previous_block = sequence[index - 1] if index > 0 else None
                next_block = sequence[index + 1] if index + 1 < len(sequence) else None
                if previous_block is None and next_block is None:
                    continue

                sample_size += 1
                if previous_block is not None:
                    before_counts[previous_block.release.id] += 1
                if next_block is not None:
                    after_counts[next_block.release.id] += 1
                mood_counts[
                    (
                        previous_block.primary_mood if previous_block is not None else None,
                        block.primary_mood,
                        next_block.primary_mood if next_block is not None else None,
                    )
                ] += 1

        return RecordFlowInsights(
            release_id=release_id,
            before=self._release_flow_summaries(before_counts, release_by_id, limit),
            after=self._release_flow_summaries(after_counts, release_by_id, limit),
            mood_transitions=[
                RecordFlowMoodTransition(
                    previous_mood=previous_mood,
                    current_mood=current_mood,
                    next_mood=next_mood,
                    count=count,
                )
                for (previous_mood, current_mood, next_mood), count in mood_counts.most_common(limit)
            ],
            sample_size=sample_size,
            confidence=self._flow_confidence(sample_size),
        )

    @staticmethod
    def _flow_sequences(items: list[_RecordFlowItem]) -> list[list[_RecordFlowBlock]]:
        timed_groups: dict[str, list[_RecordFlowItem]] = {}
        standalone_items: list[_RecordFlowItem] = []
        for item in items:
            if item.session.session_group_id:
                timed_groups.setdefault(item.session.session_group_id, []).append(item)
            else:
                standalone_items.append(item)

        sequences = [
            SessionsService._collapse_release_blocks(sorted(group_items, key=SessionsService._flow_item_time))
            for group_items in timed_groups.values()
        ]

        current_standalone_sequence: list[_RecordFlowItem] = []
        for item in sorted(standalone_items, key=SessionsService._flow_item_time):
            if current_standalone_sequence:
                gap = SessionsService._flow_item_time(item) - SessionsService._flow_item_time(
                    current_standalone_sequence[-1]
                )
                if gap > FLOW_INSIGHTS_STANDALONE_GAP:
                    sequences.append(SessionsService._collapse_release_blocks(current_standalone_sequence))
                    current_standalone_sequence = []
            current_standalone_sequence.append(item)
        if current_standalone_sequence:
            sequences.append(SessionsService._collapse_release_blocks(current_standalone_sequence))

        return [sequence for sequence in sequences if len(sequence) > 1]

    def _flow_insights_since(self, period: str) -> datetime | None:
        normalized_period = period.strip().lower()
        if normalized_period not in FLOW_INSIGHTS_PERIOD_WINDOWS:
            raise SessionValidationError("invalid_period", "period must be one of: 3m, 6m, 1y, all.")

        window = FLOW_INSIGHTS_PERIOD_WINDOWS[normalized_period]
        if window is None:
            return None
        return self._current_time() - window

    @staticmethod
    def _collapse_release_blocks(items: list[_RecordFlowItem]) -> list[_RecordFlowBlock]:
        blocks: list[_RecordFlowBlock] = []
        for item in items:
            mood = SessionsService._flow_mood(item.session.mood)
            if blocks and blocks[-1].release.id == item.release.id:
                blocks[-1].moods.append(mood)
            else:
                blocks.append(_RecordFlowBlock(release=item.release, moods=[mood]))
        return blocks

    @staticmethod
    def _release_flow_summaries(
        counts: Counter[str],
        release_by_id: dict[str, Releases],
        limit: int,
    ) -> list[RecordFlowReleaseSummary]:
        return [
            RecordFlowReleaseSummary(release=release_by_id[release_id], count=count)
            for release_id, count in counts.most_common(limit)
            if release_id in release_by_id
        ]

    @staticmethod
    def _flow_confidence(sample_size: int) -> str:
        if sample_size >= 10:
            return "high"
        if sample_size >= 3:
            return "medium"
        return "low"

    @staticmethod
    def _flow_mood(mood: str | None) -> str | None:
        if mood is None:
            return None
        stripped = mood.strip()
        return stripped or None

    @staticmethod
    def _flow_item_time(item: _RecordFlowItem) -> datetime:
        return item.session.played_at or item.session.created_at

    def get_home_summary(
        self,
        db: Session,
        *,
        recent_limit: int = 5,
        top_limit: int = 3,
    ) -> HomeSummary:
        if recent_limit < 1 or recent_limit > self._max_page_limit:
            logger.info("Rejecting home summary invalid_recent_limit=%s", recent_limit)
            raise SessionValidationError(
                "invalid_limit",
                f"recent_limit must be between 1 and {self._max_page_limit}.",
            )
        if top_limit < 1 or top_limit > self._max_page_limit:
            logger.info("Rejecting home summary invalid_top_limit=%s", top_limit)
            raise SessionValidationError("invalid_limit", f"top_limit must be between 1 and {self._max_page_limit}.")

        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        recent_sessions = [
            SessionReleaseSummary(session=session, release=release)
            for session, release in self._sessions_repository.get_recent_with_releases(db, limit=recent_limit)
        ]
        top_records = [
            TopReleaseSummary(
                release=release,
                plays=int(plays),
                average_rating=float(average_rating) if average_rating else None,
            )
            for release, plays, average_rating in self._sessions_repository.get_top_release_stats(db, limit=top_limit)
        ]
        return HomeSummary(
            recent_sessions=recent_sessions,
            total_sessions=self._sessions_repository.count_all(db),
            records_this_month=self._sessions_repository.count_distinct_releases_since(db, since=month_start),
            top_records=top_records,
        )

    def list_custom_moods(self, db: Session) -> list[SessionsMoods]:
        return self._moods_repository.get_custom(db)

    def create_custom_mood(self, db: Session, name: str) -> SessionsMoods:
        normalized_name = self._normalize_custom_mood_name(name)
        existing_mood = self._moods_repository.get_by_name(db, normalized_name)
        if existing_mood is not None:
            raise SessionMoodAlreadyExistsError(normalized_name)
        canonical_name = self._sessions_repository.get_mood_by_name(db, normalized_name) or normalized_name
        return self._moods_repository.create_custom(db, canonical_name)

    def delete_custom_mood(self, db: Session, name: str) -> None:
        normalized_name = self._normalize_custom_mood_name(name)
        self._moods_repository.delete_custom(db, normalized_name)

    def _validate_create_input(
        self,
        db: Session,
        *,
        release_id: str,
        rating: int | None,
        mood: str | None,
        notes: str | None,
        played_at: str,
        side: str | None,
        track_positions: list[str] | None,
        session_group_id: str | None,
    ) -> CreateSessionData:
        if rating is not None and not 1 <= rating <= 5:
            logger.info("Rejecting session create release_id=%s invalid_rating=%s", release_id, rating)
            raise SessionValidationError("invalid_rating", "Rating must be between 1 and 5.")

        normalized_played_at = self._parse_played_at(played_at)
        normalized_side = self._normalize_side(side)
        normalized_mood = self._canonicalize_session_mood(db, mood)
        normalized_notes = self._normalize_optional_text(notes)

        release = self._releases_repository.get_by_id(db, release_id)
        if release is None:
            logger.info("Release not found during session create release_id=%s", release_id)
            raise ReleaseNotFoundError(release_id)
        if not release.in_collection and release.collection_removed_at is not None:
            logger.info("Rejecting session create for inactive collection release_id=%s", release_id)
            raise SessionValidationError(
                "release_not_in_collection",
                "Release must be added back to collection before logging a new session.",
            )

        self._validate_release_side(db, release=release, normalized_side=normalized_side, context_id=release_id)
        normalized_session_group_id = self._session_groups_service.validate_active_session_group(db, session_group_id)
        tracks = self._validate_track_selection(
            db,
            release=release,
            normalized_side=normalized_side,
            track_positions=track_positions,
        )

        return CreateSessionData(
            release_id=release_id,
            session_group_id=normalized_session_group_id,
            rating=rating,
            mood=normalized_mood,
            notes=normalized_notes,
            played_at=normalized_played_at,
            side=normalized_side,
            tracks=tracks,
        )

    def _validate_update_input(
        self,
        db: Session,
        *,
        session: Sessions,
        fields: dict[str, Any],
    ) -> UpdateSessionData:
        rating = fields.get("rating", session.rating)
        if rating is not None and not 1 <= rating <= 5:
            logger.info("Rejecting session update session_id=%s invalid_rating=%s", session.id, rating)
            raise SessionValidationError("invalid_rating", "Rating must be between 1 and 5.")

        normalized_side = self._normalize_side(fields["side"]) if "side" in fields else session.vinyl_side
        normalized_mood = self._canonicalize_session_mood(db, fields["mood"]) if "mood" in fields else session.mood
        normalized_notes = self._normalize_optional_text(fields["notes"]) if "notes" in fields else session.notes

        release = self._releases_repository.get_by_id(db, session.release_id)
        if release is None:
            raise ReleaseNotFoundError(session.release_id)

        self._validate_release_side(db, release=release, normalized_side=normalized_side, context_id=session.id)
        tracks = (
            self._validate_track_selection(
                db,
                release=release,
                normalized_side=normalized_side,
                track_positions=fields["track_positions"],
            )
            if "track_positions" in fields
            else None
        )

        return UpdateSessionData(
            rating=rating,
            mood=normalized_mood,
            notes=normalized_notes,
            side=normalized_side,
            tracks=tracks,
        )

    def _validate_release_side(
        self,
        db: Session,
        *,
        release: Releases,
        normalized_side: str | None,
        context_id: str,
    ) -> None:
        if normalized_side is None:
            return

        cache_entry = self._discogs_repository.get_by_discogs_release_id(db, release.discogs_release_id)
        available_sides = self._extract_release_sides(cache_entry.raw_discogs_json if cache_entry is not None else None)
        if available_sides and normalized_side not in available_sides:
            logger.info(
                "Rejecting session side context_id=%s invalid_side=%s available_sides=%s",
                context_id,
                normalized_side,
                sorted(available_sides),
            )
            raise SessionValidationError(
                "invalid_side",
                f"Side '{normalized_side}' does not exist for release '{release.id}'.",
            )

    def _validate_track_selection(
        self,
        db: Session,
        *,
        release: Releases,
        normalized_side: str | None,
        track_positions: list[str] | None,
    ) -> list[SessionTrackSelection]:
        normalized_positions = self._normalize_track_positions(track_positions)
        if not normalized_positions:
            return []
        if normalized_side is None:
            raise SessionValidationError("invalid_tracks", "Track selection requires a selected side.")

        cache_entry = self._discogs_repository.get_by_discogs_release_id(db, release.discogs_release_id)
        tracklist = extract_release_tracklist(cache_entry.raw_discogs_json if cache_entry is not None else None)
        if not tracklist:
            raise SessionValidationError("invalid_tracks", "Track selection requires cached Discogs tracklist data.")

        tracks_by_position: dict[str, list[tuple[int, ReleaseTrackData]]] = {}
        for sequence, track in enumerate(tracklist, start=1):
            tracks_by_position.setdefault(track.position.strip().upper(), []).append((sequence, track))

        selected_tracks: list[SessionTrackSelection] = []
        for position in normalized_positions:
            matches = tracks_by_position.get(position)
            if not matches:
                raise SessionValidationError(
                    "invalid_tracks",
                    f"Track '{position}' does not exist for release '{release.id}'.",
                )
            if len(matches) > 1:
                raise SessionValidationError(
                    "invalid_tracks",
                    f"Track '{position}' is ambiguous for release '{release.id}'.",
                )

            sequence, track = matches[0]
            if not self._track_belongs_to_side(track.position, normalized_side):
                raise SessionValidationError(
                    "invalid_tracks",
                    f"Track '{track.position}' is not on side '{normalized_side}'.",
                )
            selected_tracks.append(
                SessionTrackSelection(
                    position=track.position,
                    artist=_display_track_artists(track.artists),
                    title=track.title,
                    duration=track.duration,
                    sequence=sequence,
                )
            )

        return sorted(selected_tracks, key=lambda track: track.sequence)

    def _normalize_track_positions(self, value: list[str] | None) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise SessionValidationError("invalid_tracks", "Track positions must be a list.")

        normalized_positions: list[str] = []
        seen_positions: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise SessionValidationError("invalid_tracks", "Track positions must be text.")
            normalized = item.strip().upper()
            if not normalized:
                raise SessionValidationError("invalid_tracks", "Track positions cannot be blank.")
            if normalized in seen_positions:
                raise SessionValidationError("invalid_tracks", f"Track '{normalized}' was selected more than once.")
            seen_positions.add(normalized)
            normalized_positions.append(normalized)
        return normalized_positions

    def _track_belongs_to_side(self, track_position: str, normalized_side: str) -> bool:
        expected_side = normalized_side.split(":")[-1]
        return self._track_side_prefix(track_position) == expected_side

    def _enrich_track_artists(
        self,
        db: Session,
        release: Releases | None,
        tracks: list[SessionTracks],
        *,
        lookup_cache: dict[int, tuple[dict[tuple[str, str], str], dict[str, str]]] | None = None,
    ) -> list[SessionTrackSnapshot]:
        if release is None or all(track.track_artist for track in tracks):
            return [_session_track_snapshot(track) for track in tracks]

        cache = lookup_cache if lookup_cache is not None else {}
        if release.discogs_release_id not in cache:
            cache[release.discogs_release_id] = self._cached_track_artist_lookup(db, release.discogs_release_id)
        artist_by_key, artist_by_position = cache[release.discogs_release_id]
        return [
            _session_track_snapshot(
                track,
                artist=(
                    track.track_artist
                    or artist_by_key.get(_track_artist_key(track.track_position, track.track_title))
                    or artist_by_position.get(_normalize_track_position(track.track_position))
                ),
            )
            for track in tracks
        ]

    def _cached_track_artist_lookup(
        self,
        db: Session,
        discogs_release_id: int,
    ) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
        cache_entry = self._discogs_repository.get_by_discogs_release_id(db, discogs_release_id)
        tracklist = extract_release_tracklist(cache_entry.raw_discogs_json if cache_entry is not None else None)
        artist_by_key: dict[tuple[str, str], str] = {}
        artists_by_position: dict[str, set[str]] = {}
        for track in tracklist:
            artist = _display_track_artists(track.artists)
            if not artist:
                continue
            artist_by_key[_track_artist_key(track.position, track.title)] = artist
            artists_by_position.setdefault(_normalize_track_position(track.position), set()).add(artist)

        artist_by_position = {
            position: next(iter(artists)) for position, artists in artists_by_position.items() if len(artists) == 1
        }
        return artist_by_key, artist_by_position

    def _track_side_prefix(self, track_position: str) -> str | None:
        letters: list[str] = []
        for character in track_position.strip().upper():
            if character.isalpha():
                letters.append(character)
                continue
            if letters:
                break
        return "".join(letters) or None

    def _parse_played_at(self, value: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            logger.info("Rejecting session create invalid_played_at=%s", value)
            raise SessionValidationError("invalid_played_at", "played_at must be a valid ISO8601 datetime.")

        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as error:
            logger.info("Rejecting session create invalid_played_at=%s", value)
            raise SessionValidationError(
                "invalid_played_at",
                "played_at must be a valid ISO8601 datetime.",
            ) from error

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)

        return parsed

    def _normalize_side(self, value: str | None) -> str | None:
        normalized = self._normalize_optional_text(value)
        return normalized.upper() if normalized is not None else None

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    def _normalize_custom_mood_name(self, value: str) -> str:
        if not isinstance(value, str):
            raise SessionValidationError("invalid_mood", "Mood name must be text.")

        normalized = " ".join(value.strip().split())
        if not CUSTOM_MOOD_MIN_LENGTH <= len(normalized) <= CUSTOM_MOOD_MAX_LENGTH:
            raise SessionValidationError(
                "invalid_mood",
                f"Mood name must be between {CUSTOM_MOOD_MIN_LENGTH} and {CUSTOM_MOOD_MAX_LENGTH} characters.",
            )
        if any(not (character.isalnum() or character.isspace()) for character in normalized):
            raise SessionValidationError("invalid_mood", "Mood name must use only letters, numbers, and spaces.")
        if normalized.lower() in BUILT_IN_SESSION_MOODS:
            raise SessionValidationError("invalid_mood", "Mood name already exists as a built-in mood.")
        return normalized

    def _canonicalize_session_mood(self, db: Session, value: str | None) -> str | None:
        normalized = self._normalize_optional_text(value)
        if normalized is None:
            return None

        built_in_mood = self._built_in_mood_name(normalized)
        if built_in_mood is not None:
            return built_in_mood

        custom_mood = self._moods_repository.get_by_name(db, normalized)
        if custom_mood is not None:
            return custom_mood.name

        historical_mood = self._sessions_repository.get_mood_by_name(db, normalized)
        return historical_mood or normalized

    def _built_in_mood_name(self, value: str) -> str | None:
        normalized = value.strip().lower()
        return BUILT_IN_SESSION_MOODS.get(normalized)

    def _extract_release_sides(self, raw_discogs_json: dict[str, Any] | None) -> set[str]:
        available_values: set[str] = set()
        for option in extract_release_side_options(raw_discogs_json):
            available_values.add(option.side)
            available_values.add(option.value)
        return available_values

    def _current_time(self) -> datetime:
        return self._as_aware_utc(self._now_provider())

    @staticmethod
    def _as_aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _display_track_artists(artists: list[ReleaseTrackArtistData]) -> str | None:
    parts: list[str] = []
    for index, artist in enumerate(artists):
        name = artist.name.strip()
        if not name:
            continue
        if index > 0:
            join = artists[index - 1].join
            parts.append(f" {join.strip()} " if join and join.strip() else ", ")
        parts.append(name)
    return "".join(parts).strip() or None


def _session_track_snapshot(track: SessionTracks, *, artist: str | None = None) -> SessionTrackSnapshot:
    return SessionTrackSnapshot(
        track_position=track.track_position,
        track_artist=artist if artist is not None else track.track_artist,
        track_title=track.track_title,
        track_duration=track.track_duration,
        track_sequence=track.track_sequence,
    )


def _track_artist_key(position: str, title: str) -> tuple[str, str]:
    return _normalize_track_position(position), " ".join(title.strip().casefold().split())


def _normalize_track_position(position: str) -> str:
    return position.strip().upper()
