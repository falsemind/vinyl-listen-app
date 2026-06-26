from datetime import UTC, datetime

import pytest

from app.models.sessions import SessionGroups
from app.services.session_groups_service import (
    SessionGroupAlreadyActiveError,
    SessionGroupEditWindowExpiredError,
    SessionGroupInactiveError,
    SessionGroupsService,
    SessionGroupValidationError,
)


class InMemorySessionGroupsRepository:
    def __init__(self, active_group: SessionGroups | None = None) -> None:
        self.active_group = active_group
        self.created_payload: dict | None = None
        self.finished_payload: tuple[str, datetime] | None = None
        self.groups: dict[str, SessionGroups] = {}
        if active_group is not None:
            self.groups[active_group.id] = active_group

    def create(
        self,
        _db,
        *,
        user_id: str | None = None,
        title: str | None,
        style_focus: str,
        mood_direction: str,
        session_type: str,
        notes: str | None,
        started_at: datetime,
    ) -> SessionGroups:
        self.created_payload = {
            "user_id": user_id,
            "title": title,
            "style_focus": style_focus,
            "mood_direction": mood_direction,
            "session_type": session_type,
            "notes": notes,
            "started_at": started_at,
        }
        group = SessionGroups(
            id="group-123",
            user_id=user_id,
            title=title,
            status="active",
            style_focus=style_focus,
            mood_direction=mood_direction,
            session_type=session_type,
            notes=notes,
            started_at=started_at,
            created_at=started_at,
            updated_at=started_at,
        )
        self.active_group = group
        self.groups[group.id] = group
        return group

    def get_by_id(self, _db, session_group_id: str, *, user_id: str | None = None) -> SessionGroups | None:
        _ = user_id
        return self.groups.get(session_group_id)

    def get_active(self, _db, *, user_id: str | None = None) -> SessionGroups | None:
        _ = user_id
        return self.active_group

    def finish(
        self,
        _db,
        session_group: SessionGroups,
        *,
        ended_at: datetime,
        notes: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> SessionGroups:
        self.finished_payload = (session_group.id, ended_at)
        session_group.status = "completed"
        session_group.ended_at = ended_at
        if notes is not None:
            session_group.notes = notes
        if metadata:
            for field, value in metadata.items():
                setattr(session_group, field, value)
        session_group.updated_at = ended_at
        if self.active_group is session_group:
            self.active_group = None
        return session_group

    def update(self, _db, session_group: SessionGroups, *, fields: dict, updated_at: datetime) -> SessionGroups:
        for field, value in fields.items():
            setattr(session_group, field, value)
        session_group.updated_at = updated_at
        return session_group


class InMemorySessionsRepository:
    def __init__(self, latest_created_at_by_group_id: dict[str, datetime] | None = None) -> None:
        self.latest_created_at_by_group_id = latest_created_at_by_group_id or {}

    def get_latest_created_at_by_session_group_id(
        self,
        _db,
        session_group_id: str,
        *,
        user_id: str | None = None,
    ) -> datetime | None:
        _ = user_id
        return self.latest_created_at_by_group_id.get(session_group_id)


class RecordingAuthRepository:
    def __init__(self) -> None:
        self.locked_user_ids: list[str] = []

    def lock_user_by_id(self, _db, user_id: str):
        self.locked_user_ids.append(user_id)
        return


def test_start_session_group_creates_active_group_with_normalized_title() -> None:
    repository = InMemorySessionGroupsRepository()
    service = SessionGroupsService(
        session_groups_repository=repository,
        now_provider=lambda: datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )

    group = service.start_session_group(db=object(), title="  Late night stack  ")

    assert group.id == "group-123"
    assert group.title == "Late night stack"
    assert group.status == "active"
    assert repository.created_payload == {
        "user_id": None,
        "title": "Late night stack",
        "style_focus": "mixed",
        "mood_direction": "steady_mood",
        "session_type": "casual_listening",
        "notes": None,
        "started_at": datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    }


def test_start_session_group_locks_user_for_account_mutation() -> None:
    repository = InMemorySessionGroupsRepository()
    auth_repository = RecordingAuthRepository()
    service = SessionGroupsService(
        session_groups_repository=repository,
        auth_repository=auth_repository,
        now_provider=lambda: datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )

    group = service.start_session_group(db=object(), user_id="user-123", title="Late night stack")

    assert auth_repository.locked_user_ids == ["user-123"]
    assert group.user_id == "user-123"
    assert repository.created_payload["user_id"] == "user-123"


def test_start_session_group_accepts_metadata() -> None:
    repository = InMemorySessionGroupsRepository()
    service = SessionGroupsService(
        session_groups_repository=repository,
        now_provider=lambda: datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )

    group = service.start_session_group(
        db=object(),
        title=None,
        style_focus="one_style",
        mood_direction="energy_build",
        session_type="dj_set",
        notes="  Warm up shelf.  ",
    )

    assert group.style_focus == "one_style"
    assert group.mood_direction == "energy_build"
    assert group.session_type == "dj_set"
    assert group.notes == "Warm up shelf."
    assert repository.created_payload == {
        "user_id": None,
        "title": None,
        "style_focus": "one_style",
        "mood_direction": "energy_build",
        "session_type": "dj_set",
        "notes": "Warm up shelf.",
        "started_at": datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    }


def test_start_session_group_rejects_notes_over_500_characters() -> None:
    service = SessionGroupsService(
        session_groups_repository=InMemorySessionGroupsRepository(),
        now_provider=lambda: datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )

    with pytest.raises(SessionGroupValidationError) as error:
        service.start_session_group(
            db=object(),
            title=None,
            notes="x" * 501,
        )

    assert error.value.code == "invalid_notes"
    assert error.value.message == "notes must be 500 characters or fewer."


def test_start_session_group_rejects_existing_active_group() -> None:
    active_group = SessionGroups(
        id="group-123",
        title=None,
        status="active",
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    service = SessionGroupsService(
        session_groups_repository=InMemorySessionGroupsRepository(active_group),
        sessions_repository=InMemorySessionsRepository(),
        now_provider=lambda: datetime(2026, 4, 19, 8, 10, tzinfo=UTC),
    )

    with pytest.raises(SessionGroupAlreadyActiveError) as exc_info:
        service.start_session_group(db=object(), title=None)

    assert exc_info.value.session_group_id == "group-123"


def test_start_session_group_expires_stale_active_group_before_creating_new_group() -> None:
    active_group = SessionGroups(
        id="stale-group",
        title=None,
        status="active",
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    repository = InMemorySessionGroupsRepository(active_group)
    service = SessionGroupsService(
        session_groups_repository=repository,
        sessions_repository=InMemorySessionsRepository({"stale-group": datetime(2026, 4, 19, 8, 5, tzinfo=UTC)}),
        now_provider=lambda: datetime(2026, 4, 19, 8, 40, tzinfo=UTC),
    )

    group = service.start_session_group(db=object(), title="Next stack")

    assert active_group.status == "completed"
    assert active_group.ended_at == datetime(2026, 4, 19, 8, 35, tzinfo=UTC)
    assert group.title == "Next stack"
    assert repository.finished_payload == ("stale-group", datetime(2026, 4, 19, 8, 35, tzinfo=UTC))


def test_get_active_session_group_auto_finishes_after_inactivity() -> None:
    active_group = SessionGroups(
        id="group-123",
        title=None,
        status="active",
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    repository = InMemorySessionGroupsRepository(active_group)
    service = SessionGroupsService(
        session_groups_repository=repository,
        sessions_repository=InMemorySessionsRepository(),
        now_provider=lambda: datetime(2026, 4, 19, 8, 30, tzinfo=UTC),
    )

    group = service.get_active_session_group(db=object())

    assert group is None
    assert active_group.status == "completed"
    assert active_group.ended_at == datetime(2026, 4, 19, 8, 30, tzinfo=UTC)


def test_validate_active_session_group_rejects_auto_expired_group() -> None:
    active_group = SessionGroups(
        id="group-123",
        title=None,
        status="active",
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    repository = InMemorySessionGroupsRepository(active_group)
    service = SessionGroupsService(
        session_groups_repository=repository,
        sessions_repository=InMemorySessionsRepository({"group-123": datetime(2026, 4, 19, 8, 1, tzinfo=UTC)}),
        now_provider=lambda: datetime(2026, 4, 19, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(SessionGroupInactiveError):
        service.validate_active_session_group(db=object(), session_group_id="group-123")

    assert active_group.status == "completed"
    assert active_group.ended_at == datetime(2026, 4, 19, 8, 31, tzinfo=UTC)


def test_finish_session_group_marks_active_group_completed() -> None:
    active_group = SessionGroups(
        id="group-123",
        title="Late night stack",
        status="active",
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    repository = InMemorySessionGroupsRepository(active_group)
    service = SessionGroupsService(
        session_groups_repository=repository,
        sessions_repository=InMemorySessionsRepository(),
        now_provider=lambda: datetime(2026, 4, 19, 8, 10, tzinfo=UTC),
    )

    group = service.finish_session_group(
        db=object(),
        session_group_id="group-123",
        ended_at="2026-04-19T09:00:00Z",
    )

    assert group.status == "completed"
    assert group.ended_at == datetime(2026, 4, 19, 9, 0, tzinfo=UTC)
    assert repository.finished_payload == ("group-123", datetime(2026, 4, 19, 9, 0, tzinfo=UTC))


def test_finish_session_group_rejects_inactive_group() -> None:
    completed_group = SessionGroups(
        id="group-123",
        title=None,
        status="completed",
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    service = SessionGroupsService(
        session_groups_repository=InMemorySessionGroupsRepository(completed_group),
        sessions_repository=InMemorySessionsRepository(),
    )

    with pytest.raises(SessionGroupInactiveError):
        service.finish_session_group(db=object(), session_group_id="group-123")


def test_finish_session_group_rejects_ended_at_before_started_at() -> None:
    active_group = SessionGroups(
        id="group-123",
        title=None,
        status="active",
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    service = SessionGroupsService(
        session_groups_repository=InMemorySessionGroupsRepository(active_group),
        sessions_repository=InMemorySessionsRepository(),
        now_provider=lambda: datetime(2026, 4, 19, 8, 10, tzinfo=UTC),
    )

    with pytest.raises(SessionGroupValidationError) as exc_info:
        service.finish_session_group(
            db=object(),
            session_group_id="group-123",
            ended_at="2026-04-19T07:59:00Z",
        )

    assert exc_info.value.code == "invalid_ended_at"


def test_finish_session_group_saves_metadata_and_notes() -> None:
    active_group = SessionGroups(
        id="group-123",
        title="Late night stack",
        status="active",
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    service = SessionGroupsService(
        session_groups_repository=InMemorySessionGroupsRepository(active_group),
        sessions_repository=InMemorySessionsRepository(),
        now_provider=lambda: datetime(2026, 4, 19, 8, 10, tzinfo=UTC),
    )

    group = service.finish_session_group(
        db=object(),
        session_group_id="group-123",
        ended_at="2026-04-19T09:00:00Z",
        style_focus="one_style",
        mood_direction="mood_switch",
        session_type="rediscovery",
        notes="  Pulled older favorites.  ",
    )

    assert group.style_focus == "one_style"
    assert group.mood_direction == "mood_switch"
    assert group.session_type == "rediscovery"
    assert group.notes == "Pulled older favorites."


def test_update_session_group_edits_completed_group_inside_window() -> None:
    group = SessionGroups(
        id="group-123",
        title="Late night stack",
        status="completed",
        style_focus="mixed",
        mood_direction="steady_mood",
        session_type="casual_listening",
        ended_at=datetime(2026, 4, 19, 9, 0, tzinfo=UTC),
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    service = SessionGroupsService(
        session_groups_repository=InMemorySessionGroupsRepository(group),
        sessions_repository=InMemorySessionsRepository(),
        now_provider=lambda: datetime(2026, 4, 19, 9, 10, tzinfo=UTC),
    )

    updated = service.update_session_group(
        db=object(),
        session_group_id="group-123",
        fields={
            "style_focus": "random",
            "mood_direction": "cool_down",
            "session_type": "background",
            "notes": "  Gentle finish.  ",
        },
    )

    assert updated.style_focus == "random"
    assert updated.mood_direction == "cool_down"
    assert updated.session_type == "background"
    assert updated.notes == "Gentle finish."
    assert updated.updated_at == datetime(2026, 4, 19, 9, 10, tzinfo=UTC)


def test_update_session_group_rejects_completed_group_after_edit_window() -> None:
    group = SessionGroups(
        id="group-123",
        title="Late night stack",
        status="completed",
        ended_at=datetime(2026, 4, 19, 9, 0, tzinfo=UTC),
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    service = SessionGroupsService(
        session_groups_repository=InMemorySessionGroupsRepository(group),
        sessions_repository=InMemorySessionsRepository(),
        now_provider=lambda: datetime(2026, 4, 19, 9, 16, tzinfo=UTC),
    )

    with pytest.raises(SessionGroupEditWindowExpiredError) as exc_info:
        service.update_session_group(db=object(), session_group_id="group-123", fields={"notes": "Too late"})

    assert exc_info.value.code == "session_group_edit_window_expired"


def test_update_session_group_rejects_invalid_metadata() -> None:
    group = SessionGroups(
        id="group-123",
        title="Late night stack",
        status="active",
        started_at=datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    )
    service = SessionGroupsService(
        session_groups_repository=InMemorySessionGroupsRepository(group),
        sessions_repository=InMemorySessionsRepository(),
        now_provider=lambda: datetime(2026, 4, 19, 8, 10, tzinfo=UTC),
    )

    with pytest.raises(SessionGroupValidationError) as exc_info:
        service.update_session_group(db=object(), session_group_id="group-123", fields={"session_type": "archive"})

    assert exc_info.value.code == "invalid_session_type"
