from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.sessions import SessionGroups
from app.repositories.session_groups_repository import SessionGroupsRepository
from app.repositories.sessions_repository import SessionsRepository

SESSION_GROUP_INACTIVITY_TIMEOUT = timedelta(minutes=30)
SESSION_GROUP_EDIT_WINDOW = timedelta(minutes=15)
SESSION_GROUP_TITLE_MAX_LENGTH = 100
SESSION_GROUP_NOTES_MAX_LENGTH = 1000
SESSION_GROUP_STYLE_FOCUS_VALUES = {"one_style", "mixed", "random"}
SESSION_GROUP_MOOD_DIRECTION_VALUES = {"steady_mood", "mood_switch", "energy_build", "cool_down"}
SESSION_GROUP_TYPE_VALUES = {
    "dj_set",
    "casual_listening",
    "rediscovery",
    "testing_records",
    "background",
}
SESSION_GROUP_METADATA_FIELDS = {
    "style_focus": SESSION_GROUP_STYLE_FOCUS_VALUES,
    "mood_direction": SESSION_GROUP_MOOD_DIRECTION_VALUES,
    "session_type": SESSION_GROUP_TYPE_VALUES,
}
DEFAULT_SESSION_GROUP_STYLE_FOCUS = "mixed"
DEFAULT_SESSION_GROUP_MOOD_DIRECTION = "steady_mood"
DEFAULT_SESSION_GROUP_TYPE = "casual_listening"


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


class SessionGroupEditWindowExpiredError(SessionGroupServiceError):
    """Raised when a stopped timed session group can no longer be edited."""

    def __init__(self, session_group_id: str) -> None:
        super().__init__(f"Session group '{session_group_id}' can no longer be edited.")
        self.session_group_id = session_group_id
        self.code = "session_group_edit_window_expired"
        self.message = "Timed listening session can only be edited for 15 minutes after it stops."


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
        style_focus: str | None = None,
        mood_direction: str | None = None,
        session_type: str | None = None,
    ) -> SessionGroups:
        active_group = self._expire_if_inactive(db, self._session_groups_repository.get_active(db))
        if active_group is not None:
            raise SessionGroupAlreadyActiveError(active_group.id)

        return self._session_groups_repository.create(
            db,
            title=self._normalize_title(title),
            style_focus=self._normalize_metadata_value(
                "style_focus",
                style_focus,
                default=DEFAULT_SESSION_GROUP_STYLE_FOCUS,
            ),
            mood_direction=self._normalize_metadata_value(
                "mood_direction",
                mood_direction,
                default=DEFAULT_SESSION_GROUP_MOOD_DIRECTION,
            ),
            session_type=self._normalize_metadata_value(
                "session_type",
                session_type,
                default=DEFAULT_SESSION_GROUP_TYPE,
            ),
            started_at=self._parse_optional_datetime(started_at, field_name="started_at") or self._current_time(),
        )

    def get_active_session_group(self, db: Session) -> SessionGroups | None:
        return self._expire_if_inactive(db, self._session_groups_repository.get_active(db))

    def get_session_group(self, db: Session, session_group_id: str) -> SessionGroups:
        session_group = self._session_groups_repository.get_by_id(db, session_group_id)
        if session_group is None:
            raise SessionGroupNotFoundError(session_group_id)
        return session_group

    def get_session_groups_by_ids(self, db: Session, session_group_ids: list[str]) -> list[SessionGroups]:
        unique_ids = list(dict.fromkeys(session_group_ids))
        return self._session_groups_repository.get_by_ids(db, unique_ids)

    def finish_session_group(
        self,
        db: Session,
        session_group_id: str,
        *,
        ended_at: str | None = None,
        style_focus: str | None = None,
        mood_direction: str | None = None,
        session_type: str | None = None,
        notes: str | None = None,
    ) -> SessionGroups:
        session_group = self.get_session_group(db, session_group_id)
        if session_group.status != "active":
            raise SessionGroupInactiveError(session_group_id)
        if self._expire_if_inactive(db, session_group) is None:
            raise SessionGroupInactiveError(session_group_id)

        normalized_ended_at = self._parse_optional_datetime(ended_at, field_name="ended_at") or self._current_time()
        if normalized_ended_at < self._as_aware_utc(session_group.started_at):
            raise SessionGroupValidationError("invalid_ended_at", "ended_at must be after started_at.")

        return self._session_groups_repository.finish(
            db,
            session_group,
            ended_at=normalized_ended_at,
            notes=self._normalize_notes(notes),
            metadata=self._normalize_metadata_fields(
                {
                    "style_focus": style_focus,
                    "mood_direction": mood_direction,
                    "session_type": session_type,
                }
            ),
        )

    def validate_active_session_group(self, db: Session, session_group_id: str | None) -> str | None:
        if session_group_id is None:
            return None

        session_group = self.get_session_group(db, session_group_id)
        if session_group.status != "active":
            raise SessionGroupInactiveError(session_group_id)
        if self._expire_if_inactive(db, session_group) is None:
            raise SessionGroupInactiveError(session_group_id)
        return session_group.id

    def update_session_group(
        self,
        db: Session,
        session_group_id: str,
        *,
        fields: dict,
    ) -> SessionGroups:
        session_group = self.get_session_group(db, session_group_id)
        if not self.can_edit_session_group(session_group):
            raise SessionGroupEditWindowExpiredError(session_group_id)

        normalized_fields = self._normalize_update_fields(fields)
        return self._session_groups_repository.update(
            db,
            session_group,
            fields=normalized_fields,
            updated_at=self._current_time(),
        )

    def can_edit_session_group(self, session_group: SessionGroups) -> bool:
        editable_until = self.editable_until(session_group)
        return editable_until is None or self._current_time() <= editable_until

    def editable_until(self, session_group: SessionGroups) -> datetime | None:
        if session_group.ended_at is None:
            return None
        return self._as_aware_utc(session_group.ended_at) + SESSION_GROUP_EDIT_WINDOW

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

    def _normalize_update_fields(self, fields: dict) -> dict:
        normalized_fields: dict = {}
        for field, value in fields.items():
            if field in SESSION_GROUP_METADATA_FIELDS:
                normalized_fields[field] = self._normalize_metadata_value(field, value)
            elif field == "notes":
                normalized_fields[field] = self._normalize_notes(value)
            else:
                raise SessionGroupValidationError("invalid_field", f"{field} cannot be updated.")
        return normalized_fields

    def _normalize_metadata_fields(self, fields: dict[str, str | None]) -> dict[str, str]:
        return {
            field: self._normalize_metadata_value(field, value) for field, value in fields.items() if value is not None
        }

    @staticmethod
    def _normalize_metadata_value(field: str, value: str | None, *, default: str | None = None) -> str:
        if value is None:
            if default is not None:
                return default
            raise SessionGroupValidationError(f"invalid_{field}", f"{field} is required.")
        normalized = value.strip().lower()
        allowed_values = SESSION_GROUP_METADATA_FIELDS[field]
        if normalized not in allowed_values:
            allowed = ", ".join(sorted(allowed_values))
            raise SessionGroupValidationError(f"invalid_{field}", f"{field} must be one of: {allowed}.")
        return normalized

    @staticmethod
    def _normalize_notes(notes: str | None) -> str | None:
        if notes is None:
            return None
        normalized = notes.strip()
        if not normalized:
            return None
        if len(normalized) > SESSION_GROUP_NOTES_MAX_LENGTH:
            raise SessionGroupValidationError(
                "invalid_notes",
                f"notes must be {SESSION_GROUP_NOTES_MAX_LENGTH} characters or fewer.",
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
