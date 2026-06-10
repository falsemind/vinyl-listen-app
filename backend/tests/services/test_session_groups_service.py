from datetime import UTC, datetime

import pytest

from app.models.sessions import SessionGroups
from app.services.session_groups_service import (
    SessionGroupAlreadyActiveError,
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

    def create(self, _db, *, title: str | None, started_at: datetime) -> SessionGroups:
        self.created_payload = {"title": title, "started_at": started_at}
        group = SessionGroups(
            id="group-123",
            title=title,
            status="active",
            started_at=started_at,
            created_at=started_at,
            updated_at=started_at,
        )
        self.active_group = group
        self.groups[group.id] = group
        return group

    def get_by_id(self, _db, session_group_id: str) -> SessionGroups | None:
        return self.groups.get(session_group_id)

    def get_active(self, _db) -> SessionGroups | None:
        return self.active_group

    def finish(self, _db, session_group: SessionGroups, *, ended_at: datetime) -> SessionGroups:
        self.finished_payload = (session_group.id, ended_at)
        session_group.status = "completed"
        session_group.ended_at = ended_at
        session_group.updated_at = ended_at
        if self.active_group is session_group:
            self.active_group = None
        return session_group


class InMemorySessionsRepository:
    def __init__(self, latest_created_at_by_group_id: dict[str, datetime] | None = None) -> None:
        self.latest_created_at_by_group_id = latest_created_at_by_group_id or {}

    def get_latest_created_at_by_session_group_id(self, _db, session_group_id: str) -> datetime | None:
        return self.latest_created_at_by_group_id.get(session_group_id)


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
        "title": "Late night stack",
        "started_at": datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
    }


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
