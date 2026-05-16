import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.models.sessions import Sessions
from app.repositories.discogs_release_repository import DiscogsReleaseRepository
from app.repositories.releases_repository import ReleasesRepository
from app.repositories.sessions_repository import SessionsRepository
from app.services.release_mapper import extract_release_side_options

logger = logging.getLogger(__name__)


class SessionsServiceError(Exception):
    """Base error for listening-session service failures."""


class SessionValidationError(SessionsServiceError):
    """Raised when session input fails business-rule validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SessionNotFoundError(SessionsServiceError):
    """Raised when a session cannot be found."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' was not found.")
        self.session_id = session_id


class ReleaseNotFoundError(SessionsServiceError):
    """Raised when a release cannot be found."""

    def __init__(self, release_id: str) -> None:
        super().__init__(f"Release '{release_id}' was not found.")
        self.release_id = release_id


@dataclass(frozen=True)
class CreateSessionData:
    release_id: str
    rating: int | None
    mood: str | None
    notes: str | None
    played_at: datetime
    side: str | None


@dataclass(frozen=True)
class CreateSessionResult:
    session_id: str
    timestamp: datetime
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


class SessionsService:
    def __init__(
        self,
        sessions_repository: SessionsRepository | None = None,
        releases_repository: ReleasesRepository | None = None,
        discogs_repository: DiscogsReleaseRepository | None = None,
    ) -> None:
        self._sessions_repository = sessions_repository or SessionsRepository()
        self._releases_repository = releases_repository or ReleasesRepository()
        self._discogs_repository = discogs_repository or DiscogsReleaseRepository()

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
        )
        session = self._sessions_repository.create(
            db,
            release_id=validated.release_id,
            rating=validated.rating,
            mood=validated.mood,
            notes=validated.notes,
            played_at=validated.played_at,
            vinyl_side=validated.side,
        )
        logger.info("Created session session_id=%s release_id=%s", session.id, release_id)
        return CreateSessionResult(session_id=session.id, timestamp=session.created_at)

    def get_session(self, db: Session, session_id: str) -> Sessions:
        logger.info("Loading session session_id=%s", session_id)
        session = self._sessions_repository.get_by_id(db, session_id)
        if session is None:
            logger.info("Session not found session_id=%s", session_id)
            raise SessionNotFoundError(session_id)
        return session

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

    def get_home_summary(
        self,
        db: Session,
        *,
        recent_limit: int = 5,
        top_limit: int = 3,
    ) -> HomeSummary:
        if recent_limit < 1 or recent_limit > 25:
            logger.info("Rejecting home summary invalid_recent_limit=%s", recent_limit)
            raise SessionValidationError("invalid_limit", "recent_limit must be between 1 and 25.")
        if top_limit < 1 or top_limit > 25:
            logger.info("Rejecting home summary invalid_top_limit=%s", top_limit)
            raise SessionValidationError("invalid_limit", "top_limit must be between 1 and 25.")

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
    ) -> CreateSessionData:
        if rating is not None and not 1 <= rating <= 5:
            logger.info("Rejecting session create release_id=%s invalid_rating=%s", release_id, rating)
            raise SessionValidationError("invalid_rating", "Rating must be between 1 and 5.")

        normalized_played_at = self._parse_played_at(played_at)
        normalized_side = self._normalize_side(side)
        normalized_mood = self._normalize_optional_text(mood)
        normalized_notes = self._normalize_optional_text(notes)

        release = self._releases_repository.get_by_id(db, release_id)
        if release is None:
            logger.info("Release not found during session create release_id=%s", release_id)
            raise ReleaseNotFoundError(release_id)

        if normalized_side is not None:
            cache_entry = self._discogs_repository.get_by_discogs_release_id(db, release.discogs_release_id)
            available_sides = self._extract_release_sides(
                cache_entry.raw_discogs_json if cache_entry is not None else None
            )
            if available_sides and normalized_side not in available_sides:
                logger.info(
                    "Rejecting session create release_id=%s invalid_side=%s available_sides=%s",
                    release_id,
                    normalized_side,
                    sorted(available_sides),
                )
                raise SessionValidationError(
                    "invalid_side",
                    f"Side '{normalized_side}' does not exist for release '{release_id}'.",
                )

        return CreateSessionData(
            release_id=release_id,
            rating=rating,
            mood=normalized_mood,
            notes=normalized_notes,
            played_at=normalized_played_at,
            side=normalized_side,
        )

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

    def _extract_release_sides(self, raw_discogs_json: dict[str, Any] | None) -> set[str]:
        available_values: set[str] = set()
        for option in extract_release_side_options(raw_discogs_json):
            available_values.add(option.side)
            available_values.add(option.value)
        return available_values
