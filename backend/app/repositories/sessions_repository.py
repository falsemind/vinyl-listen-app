from sqlalchemy.orm import Session

from app.models.sessions import Sessions


class SessionsRepository:

    @staticmethod
    def get_all(db: Session):
        return db.query(Sessions).all()
