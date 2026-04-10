from sqlalchemy.orm import Session

from app.models.releases import Releases


class ReleasesRepository:

    @staticmethod
    def get_all(db: Session):
        return db.query(Releases).all()
