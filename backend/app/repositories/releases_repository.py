from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.services.release_mapper import InternalReleaseData


class ReleasesRepository:
    @staticmethod
    def get_by_id(db: Session, release_id: str) -> Releases | None:
        return db.query(Releases).filter(Releases.id == release_id).one_or_none()

    @staticmethod
    def get_by_discogs_release_id(db: Session, discogs_release_id: int) -> Releases | None:
        return db.query(Releases).filter(Releases.discogs_release_id == discogs_release_id).one_or_none()

    @staticmethod
    def save_or_update(db: Session, data: InternalReleaseData) -> tuple[Releases, bool]:
        release = ReleasesRepository.get_by_discogs_release_id(db, data.discogs_release_id)
        created = release is None

        if release is None:
            release = Releases(
                discogs_release_id=data.discogs_release_id,
                artist=data.artist,
                title=data.title,
                year=data.year,
                label=data.label,
                catalog_number=data.catalog_number,
                barcode=data.barcode,
                genres=data.genres,
                styles=data.styles,
                cover_image_url=data.cover_image_url,
            )
        else:
            release.artist = data.artist
            release.title = data.title
            release.year = data.year
            release.label = data.label
            release.catalog_number = data.catalog_number
            release.barcode = data.barcode
            release.genres = data.genres
            release.styles = data.styles
            release.cover_image_url = data.cover_image_url

        db.add(release)
        db.commit()
        db.refresh(release)
        return release, created
