from datetime import datetime

from sqlalchemy.orm import Session

from app.models.sessions import SessionGroups


class SessionGroupsRepository:
    """Persistence operations for timed listening session groups."""

    @staticmethod
    def create(
        db: Session,
        *,
        title: str | None,
        style_focus: str,
        mood_direction: str,
        session_type: str,
        started_at: datetime,
    ) -> SessionGroups:
        session_group = SessionGroups(
            title=title,
            style_focus=style_focus,
            mood_direction=mood_direction,
            session_type=session_type,
            started_at=started_at,
            status="active",
        )
        db.add(session_group)
        db.commit()
        db.refresh(session_group)
        return session_group

    @staticmethod
    def get_by_id(db: Session, session_group_id: str) -> SessionGroups | None:
        return db.query(SessionGroups).filter(SessionGroups.id == session_group_id).first()

    @staticmethod
    def get_by_ids(db: Session, session_group_ids: list[str]) -> list[SessionGroups]:
        if not session_group_ids:
            return []
        return db.query(SessionGroups).filter(SessionGroups.id.in_(session_group_ids)).all()

    @staticmethod
    def get_active(db: Session) -> SessionGroups | None:
        return (
            db.query(SessionGroups)
            .filter(SessionGroups.status == "active")
            .order_by(SessionGroups.started_at.desc(), SessionGroups.created_at.desc())
            .first()
        )

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
