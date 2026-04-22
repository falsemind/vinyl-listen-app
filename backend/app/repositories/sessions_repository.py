from datetime import datetime

from sqlalchemy.orm import Session

from app.models.sessions import Sessions


class SessionsRepository:
    @staticmethod
    def get_by_id(db: Session, session_id: str) -> Sessions | None:
        return db.query(Sessions).filter(Sessions.id == session_id).one_or_none()

    @staticmethod
    def get_by_release_id(
        db: Session,
        release_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[Sessions]:
        return (
            db.query(Sessions)
            .filter(Sessions.release_id == release_id)
            .order_by(Sessions.played_at.desc(), Sessions.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def create(
        db: Session,
        *,
        release_id: str,
        rating: int | None,
        mood: str | None,
        notes: str | None,
        played_at: datetime,
        vinyl_side: str | None,
    ) -> Sessions:
        session = Sessions(
            release_id=release_id,
            rating=rating,
            mood=mood,
            notes=notes,
            played_at=played_at,
            vinyl_side=vinyl_side,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
