from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.sessions import SessionGroups
from app.repositories.session_groups_repository import SessionGroupsRepository
from app.repositories.sessions_repository import SessionsRepository

SESSION_GROUP_INACTIVITY_TIMEOUT = timedelta(minutes=30)
SESSION_GROUP_TITLE_MAX_LENGTH = 100


class SessionGroupServiceError(Exception):
    """Base class for timed session group service errors."""


class SessionGroupValidationError(SessionGroupServiceError):
    """Raised when timed session group input fails validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SessionGroupAlreadyActiveError(SessionGroupServiceError):
    """Raised when starting a group while another group is active."""

    def __init__(self, session_group_id: str) -> None:
        super().__init__("A timed listening session is already active.")
        self.session_group_id = session_group_id
        self.code = "session_group_active"
        self.message = "A timed listening session is already active."


class SessionGroupNotFoundError(SessionGroupServiceError):
    """Raised when a timed session group cannot be found."""

    def __init__(self, session_group_id: str) -> None:
        super().__init__(f"Session group '{session_group_id}' was not found.")
        self.session_group_id = session_group_id


class SessionGroupInactiveError(SessionGroupServiceError):
    """Raised when a stopped timed session group is used as active."""

    def __init__(self, session_group_id: str) -> None:
        super().__init__(f"Session group '{session_group_id}' is not active.")
        self.session_group_id = session_group_id
        self.code = "session_group_inactive"
        self.message = "Timed listening session is not active."


class SessionGroupsService:
    """Business logic for optional timed listening session groups."""

    def __init__(
        self,
        session_groups_repository: SessionGroupsRepository | None = None,
        sessions_repository: SessionsRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_groups_repository = session_groups_repository or SessionGroupsRepository()
        self._sessions_repository = sessions_repository or SessionsRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    def start_session_group(
        self,
        db: Session,
        *,
        title: str | None,
        started_at: str | None = None,
    ) -> SessionGroups:
        active_group = self._expire_if_inactive(db, self._session_groups_repository.get_active(db))
        if active_group is not None:
            raise SessionGroupAlreadyActiveError(active_group.id)

        return self._session_groups_repository.create(
            db,
            title=self._normalize_title(title),
            started_at=self._parse_optional_datetime(started_at, field_name="started_at") or self._current_time(),
        )

    def get_active_session_group(self, db: Session) -> SessionGroups | None:
        return self._expire_if_inactive(db, self._session_groups_repository.get_active(db))

    def get_session_group(self, db: Session, session_group_id: str) -> SessionGroups:
        session_group = self._session_groups_repository.get_by_id(db, session_group_id)
        if session_group is None:
            raise SessionGroupNotFoundError(session_group_id)
        return session_group

    def finish_session_group(
        self,
        db: Session,
        session_group_id: str,
        *,
        ended_at: str | None = None,
    ) -> SessionGroups:
        session_group = self.get_session_group(db, session_group_id)
        if session_group.status != "active":
            raise SessionGroupInactiveError(session_group_id)
        if self._expire_if_inactive(db, session_group) is None:
            raise SessionGroupInactiveError(session_group_id)

        normalized_ended_at = self._parse_optional_datetime(ended_at, field_name="ended_at") or self._current_time()
        if normalized_ended_at < self._as_aware_utc(session_group.started_at):
            raise SessionGroupValidationError("invalid_ended_at", "ended_at must be after started_at.")

        return self._session_groups_repository.finish(db, session_group, ended_at=normalized_ended_at)

    def validate_active_session_group(self, db: Session, session_group_id: str | None) -> str | None:
        if session_group_id is None:
            return None

        session_group = self.get_session_group(db, session_group_id)
        if session_group.status != "active":
            raise SessionGroupInactiveError(session_group_id)
        if self._expire_if_inactive(db, session_group) is None:
            raise SessionGroupInactiveError(session_group_id)
        return session_group.id

    def _expire_if_inactive(self, db: Session, session_group: SessionGroups | None) -> SessionGroups | None:
        if session_group is None or session_group.status != "active":
            return session_group

        last_activity_at = (
            self._sessions_repository.get_latest_created_at_by_session_group_id(db, session_group.id)
            or session_group.started_at
        )
        expires_at = self._as_aware_utc(last_activity_at) + SESSION_GROUP_INACTIVITY_TIMEOUT
        if self._current_time() < expires_at:
            return session_group

        self._session_groups_repository.finish(db, session_group, ended_at=expires_at)
        return None

    @staticmethod
    def _normalize_title(title: str | None) -> str | None:
        if title is None:
            return None
        normalized = title.strip()
        if not normalized:
            return None
        if len(normalized) > SESSION_GROUP_TITLE_MAX_LENGTH:
            raise SessionGroupValidationError(
                "invalid_title",
                f"title must be {SESSION_GROUP_TITLE_MAX_LENGTH} characters or fewer.",
            )
        return normalized

    def _parse_optional_datetime(self, value: str | None, *, field_name: str) -> datetime | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError as error:
            raise SessionGroupValidationError(
                f"invalid_{field_name}",
                f"{field_name} must be an ISO8601 datetime.",
            ) from error
        return self._as_aware_utc(parsed)

    @staticmethod
    def _as_aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _current_time(self) -> datetime:
        return self._as_aware_utc(self._now_provider())
