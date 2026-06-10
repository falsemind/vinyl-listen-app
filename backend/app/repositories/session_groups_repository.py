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
        started_at: datetime,
    ) -> SessionGroups:
        session_group = SessionGroups(
            title=title,
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
    ) -> SessionGroups:
        session_group.status = "completed"
        session_group.ended_at = ended_at
        session_group.updated_at = ended_at
        db.add(session_group)
        db.commit()
        db.refresh(session_group)
        return session_group
