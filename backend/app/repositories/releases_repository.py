from collections.abc import Sequence

from sqlalchemy import func
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
    def get_by_barcode(db: Session, barcode: str) -> Sequence[Releases]:
        normalized_barcode = barcode.strip()
        if not normalized_barcode:
            return []

        return (
            db.query(Releases)
            .filter(func.lower(Releases.barcode) == normalized_barcode.lower())
            .order_by(Releases.artist.asc(), Releases.title.asc())
            .all()
        )

    @staticmethod
    def get_by_catalog_number(db: Session, catalog_number: str) -> Sequence[Releases]:
        normalized_catalog_number = catalog_number.strip()
        if not normalized_catalog_number:
            return []

        return (
            db.query(Releases)
            .filter(func.lower(Releases.catalog_number) == normalized_catalog_number.lower())
            .order_by(Releases.artist.asc(), Releases.title.asc())
            .all()
        )

    @staticmethod
    def search_by_artist_and_title(
        db: Session,
        *,
        artist: str,
        title: str,
        limit: int = 5,
    ) -> Sequence[Releases]:
        normalized_artist = artist.strip()
        normalized_title = title.strip()
        if not normalized_artist or not normalized_title:
            return []

        return (
            db.query(Releases)
            .filter(func.lower(Releases.artist) == normalized_artist.lower())
            .filter(func.lower(Releases.title) == normalized_title.lower())
            .order_by(Releases.artist.asc(), Releases.title.asc())
            .limit(limit)
            .all()
        )

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
