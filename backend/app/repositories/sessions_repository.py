from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.releases import Releases
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
    def get_mood_by_name(db: Session, name: str) -> str | None:
        row = (
            db.query(Sessions.mood)
            .filter(Sessions.mood.isnot(None))
            .filter(Sessions.mood != "")
            .filter(func.lower(Sessions.mood) == name.lower())
            .order_by(Sessions.created_at.asc())
            .first()
        )
        return row[0] if row is not None else None

    @staticmethod
    def get_recent_with_releases(
        db: Session,
        *,
        limit: int,
    ):
        return (
            db.query(Sessions, Releases)
            .join(Releases, Sessions.release_id == Releases.id)
            .order_by(Sessions.played_at.desc(), Sessions.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_recent_notes_with_releases(
        db: Session,
        *,
        limit: int,
    ):
        return (
            db.query(Sessions, Releases)
            .join(Releases, Sessions.release_id == Releases.id)
            .filter(Sessions.notes.isnot(None))
            .filter(Sessions.notes != "")
            .order_by(Sessions.played_at.desc(), Sessions.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_all(db: Session) -> int:
        return db.query(func.count(Sessions.id)).scalar() or 0

    @staticmethod
    def count_distinct_releases_since(
        db: Session,
        *,
        since: datetime,
    ) -> int:
        return (
            db.query(func.count(func.distinct(Sessions.release_id))).filter(Sessions.played_at >= since).scalar() or 0
        )

    @staticmethod
    def get_top_release_stats(
        db: Session,
        *,
        limit: int,
    ):
        plays = func.count(Sessions.id).label("plays")
        average_rating = func.avg(Sessions.rating).label("average_rating")
        return (
            db.query(Releases, plays, average_rating)
            .join(Sessions, Sessions.release_id == Releases.id)
            .group_by(Releases.id)
            .order_by(plays.desc(), average_rating.desc())
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

    @staticmethod
    def update(
        db: Session,
        session: Sessions,
        *,
        rating: int | None,
        mood: str | None,
        notes: str | None,
        vinyl_side: str | None,
    ) -> Sessions:
        session.rating = rating
        session.mood = mood
        session.notes = notes
        session.vinyl_side = vinyl_side
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
