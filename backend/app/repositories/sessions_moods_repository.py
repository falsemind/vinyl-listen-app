from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.sessions_moods import SessionsMoods


class SessionsMoodsRepository:

    @staticmethod
    def get_all(db: Session) -> list[SessionsMoods]:
        return db.query(SessionsMoods).order_by(SessionsMoods.name.asc()).all()

    @staticmethod
    def get_custom(db: Session) -> list[SessionsMoods]:
        return (
            db.query(SessionsMoods).filter(SessionsMoods.is_custom.is_(True)).order_by(SessionsMoods.name.asc()).all()
        )

    @staticmethod
    def get_by_name(db: Session, name: str) -> SessionsMoods | None:
        return db.query(SessionsMoods).filter(func.lower(SessionsMoods.name) == name.lower()).one_or_none()

    @staticmethod
    def create_custom(db: Session, name: str) -> SessionsMoods:
        mood = SessionsMoods(name=name, is_custom=True)
        db.add(mood)
        db.commit()
        db.refresh(mood)
        return mood

    @staticmethod
    def delete_custom(db: Session, name: str) -> bool:
        mood = SessionsMoodsRepository.get_by_name(db, name)
        if mood is None or not mood.is_custom:
            return False
        db.delete(mood)
        db.commit()
        return True
