from collections.abc import Sequence
from datetime import datetime

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
    def save_or_update(db: Session, data: InternalReleaseData, *, commit: bool = True) -> tuple[Releases, bool]:
        release = ReleasesRepository.get_by_discogs_release_id(db, data.discogs_release_id)
        created = release is None

        if release is None:
            release = Releases(
                discogs_release_id=data.discogs_release_id,
                artist=data.artist,
                title=data.title,
                year=data.year,
                format=data.format,
                label=data.label,
                catalog_number=data.catalog_number,
                barcode=data.barcode,
                genres=data.genres,
                styles=data.styles,
                thumbnail_url=data.thumbnail_url,
                cover_image_url=data.cover_image_url,
            )
        else:
            release.artist = data.artist
            release.title = data.title
            release.year = data.year
            release.format = data.format
            release.label = data.label
            release.catalog_number = data.catalog_number
            release.barcode = data.barcode
            release.genres = data.genres
            release.styles = data.styles
            release.thumbnail_url = data.thumbnail_url
            release.cover_image_url = data.cover_image_url

        db.add(release)
        if commit:
            db.commit()
            db.refresh(release)
        else:
            db.flush()
        return release, created

    @staticmethod
    def mark_in_collection(
        db: Session,
        release: Releases,
        *,
        discogs_instance_id: int | None,
        collection_added_at: datetime | None,
        synced_at: datetime,
        commit: bool = True,
    ) -> Releases:
        release.in_collection = True
        release.discogs_instance_id = discogs_instance_id
        release.collection_added_at = collection_added_at
        release.collection_removed_at = None
        release.last_discogs_sync_at = synced_at

        db.add(release)
        if commit:
            db.commit()
            db.refresh(release)
        else:
            db.flush()
        return release

    @staticmethod
    def mark_missing_collection_releases_removed(
        db: Session,
        active_discogs_release_ids: set[int],
        *,
        removed_at: datetime,
        commit: bool = True,
    ) -> int:
        query = db.query(Releases).filter(Releases.in_collection.is_(True))
        if active_discogs_release_ids:
            query = query.filter(~Releases.discogs_release_id.in_(active_discogs_release_ids))

        removed_count = 0
        for release in query.all():
            release.in_collection = False
            release.collection_removed_at = removed_at
            release.last_discogs_sync_at = removed_at
            db.add(release)
            removed_count += 1

        if removed_count and commit:
            db.commit()
        elif removed_count:
            db.flush()

        return removed_count

    @staticmethod
    def list_collection_releases(
        db: Session,
        *,
        limit: int,
        offset: int,
        include_removed: bool = False,
    ) -> Sequence[Releases]:
        query = db.query(Releases)
        if not include_removed:
            query = query.filter(Releases.in_collection.is_(True))

        return (
            query.order_by(
                Releases.collection_added_at.desc().nullslast(),
                Releases.artist.asc(),
                Releases.title.asc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def search_collection_releases(
        db: Session,
        *,
        artist: str | None = None,
        title: str | None = None,
        catalog: str | None = None,
        barcode: str | None = None,
        year: int | None = None,
        limit: int,
        offset: int,
    ) -> Sequence[Releases]:
        filters = []
        if artist and artist.strip():
            filters.append(Releases.artist.ilike(f"%{artist.strip()}%"))
        if title and title.strip():
            filters.append(Releases.title.ilike(f"%{title.strip()}%"))
        if catalog and catalog.strip():
            filters.append(Releases.catalog_number.ilike(f"%{catalog.strip()}%"))
        if barcode and barcode.strip():
            filters.append(Releases.barcode.ilike(f"%{barcode.strip()}%"))
        if year is not None:
            filters.append(Releases.year == year)
        if not filters:
            return []

        return (
            db.query(Releases)
            .filter(Releases.in_collection.is_(True))
            .filter(*filters)
            .order_by(
                Releases.artist.asc(),
                Releases.title.asc(),
                Releases.year.desc().nullslast(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
