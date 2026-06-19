from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.sessions_moods import SessionsMoods


class SessionsMoodsRepository:

    @staticmethod
    def get_all(db: Session, *, user_id: str | None = None) -> list[SessionsMoods]:
        return SessionsMoodsRepository._owner_query(db, user_id=user_id).order_by(SessionsMoods.name.asc()).all()

    @staticmethod
    def get_custom(db: Session, *, user_id: str) -> list[SessionsMoods]:
        return (
            db.query(SessionsMoods)
            .filter(SessionsMoods.user_id == user_id)
            .filter(SessionsMoods.is_custom.is_(True))
            .order_by(SessionsMoods.name.asc())
            .all()
        )

    @staticmethod
    def get_by_name(db: Session, name: str, *, user_id: str | None = None) -> SessionsMoods | None:
        return (
            SessionsMoodsRepository._owner_query(db, user_id=user_id)
            .filter(func.lower(SessionsMoods.name) == name.lower())
            .order_by(SessionsMoods.user_id.is_(None).asc())
            .first()
        )

    @staticmethod
    def create_custom(db: Session, name: str, *, user_id: str) -> SessionsMoods:
        mood = SessionsMoods(name=name, user_id=user_id, is_custom=True)
        db.add(mood)
        db.commit()
        db.refresh(mood)
        return mood

    @staticmethod
    def delete_custom(db: Session, name: str, *, user_id: str) -> bool:
        mood = SessionsMoodsRepository.get_by_name(db, name, user_id=user_id)
        if mood is None or not mood.is_custom:
            return False
        db.delete(mood)
        db.commit()
        return True

    @staticmethod
    def _owner_query(db: Session, *, user_id: str | None):
        query = db.query(SessionsMoods)
        if user_id is None:
            return query.filter(SessionsMoods.user_id.is_(None))
        return query.filter((SessionsMoods.user_id == user_id) | (SessionsMoods.user_id.is_(None)))
