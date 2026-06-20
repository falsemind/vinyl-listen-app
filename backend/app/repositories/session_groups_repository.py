from datetime import datetime

from sqlalchemy.orm import Session

from app.models.sessions import SessionGroups


class SessionGroupsRepository:
    """Persistence operations for timed listening session groups."""

    @staticmethod
    def create(
        db: Session,
        *,
        user_id: str | None,
        title: str | None,
        style_focus: str,
        mood_direction: str,
        session_type: str,
        notes: str | None,
        started_at: datetime,
    ) -> SessionGroups:
        session_group = SessionGroups(
            user_id=user_id,
            title=title,
            style_focus=style_focus,
            mood_direction=mood_direction,
            session_type=session_type,
            notes=notes,
            started_at=started_at,
            status="active",
        )
        db.add(session_group)
        db.commit()
        db.refresh(session_group)
        return session_group

    @staticmethod
    def get_by_id(db: Session, session_group_id: str, *, user_id: str | None = None) -> SessionGroups | None:
        query = db.query(SessionGroups).filter(SessionGroups.id == session_group_id)
        if user_id is not None:
            query = query.filter(SessionGroups.user_id == user_id)
        return query.first()

    @staticmethod
    def get_by_ids(
        db: Session,
        session_group_ids: list[str],
        *,
        user_id: str | None = None,
    ) -> list[SessionGroups]:
        if not session_group_ids:
            return []
        query = db.query(SessionGroups).filter(SessionGroups.id.in_(session_group_ids))
        if user_id is not None:
            query = query.filter(SessionGroups.user_id == user_id)
        return query.all()

    @staticmethod
    def get_active(db: Session, *, user_id: str | None = None) -> SessionGroups | None:
        query = db.query(SessionGroups).filter(SessionGroups.status == "active")
        if user_id is not None:
            query = query.filter(SessionGroups.user_id == user_id)
        return query.order_by(SessionGroups.started_at.desc(), SessionGroups.created_at.desc()).first()

    @staticmethod
    def finish(
        db: Session,
        session_group: SessionGroups,
        *,
        ended_at: datetime,
        notes: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> SessionGroups:
        session_group.status = "completed"
        session_group.ended_at = ended_at
        if notes is not None:
            session_group.notes = notes
        if metadata:
            for field, value in metadata.items():
                setattr(session_group, field, value)
        session_group.updated_at = ended_at
        db.add(session_group)
        db.commit()
        db.refresh(session_group)
        return session_group

    @staticmethod
    def update(
        db: Session,
        session_group: SessionGroups,
        *,
        fields: dict,
        updated_at: datetime,
    ) -> SessionGroups:
        for field, value in fields.items():
            setattr(session_group, field, value)
        session_group.updated_at = updated_at
        db.add(session_group)
        db.commit()
        db.refresh(session_group)
        return session_group
