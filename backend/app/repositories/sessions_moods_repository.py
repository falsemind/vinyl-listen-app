from sqlalchemy.orm import Session

from app.models.sessions_moods import SessionsMoods


class SessionsMoodsRepository:

    @staticmethod
    def get_all(db: Session):
        return db.query(SessionsMoods).all()
