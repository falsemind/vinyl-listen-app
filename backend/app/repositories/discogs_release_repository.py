from sqlalchemy.orm import Session

from app.models.discogs_release_cache import DiscogsReleaseCache


class DiscogsReleaseRepository:

    @staticmethod
    def get_all(db: Session):
        return db.query(DiscogsReleaseCache).all()
