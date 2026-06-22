from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.releases import ManualRelease, ManualReleaseDraft
from app.schemas.manual_releases import ManualReleaseFormData

_DRAFT_CAP_LOCK_NAMESPACE = 912409


class ManualReleaseRepository:
    """Repository for user-owned manual releases and drafts."""

    def list_drafts(self, db: Session, *, user_id: str) -> list[ManualReleaseDraft]:
        return (
            db.query(ManualReleaseDraft)
            .filter(ManualReleaseDraft.user_id == user_id)
            .order_by(ManualReleaseDraft.updated_at.desc())
            .all()
        )

    def count_drafts(self, db: Session, *, user_id: str) -> int:
        return db.query(ManualReleaseDraft).filter(ManualReleaseDraft.user_id == user_id).count()

    def lock_draft_capacity_for_user(self, db: Session, *, user_id: str) -> None:
        """Serialize per-user draft cap checks on PostgreSQL."""

        bind = db.get_bind()
        if bind.dialect.name != "postgresql":
            return

        db.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:user_id))"),
            {"namespace": _DRAFT_CAP_LOCK_NAMESPACE, "user_id": user_id},
        )

    def get_draft(
        self,
        db: Session,
        draft_id: str,
        *,
        user_id: str,
        for_update: bool = False,
    ) -> ManualReleaseDraft | None:
        query = db.query(ManualReleaseDraft).filter(
            ManualReleaseDraft.id == draft_id,
            ManualReleaseDraft.user_id == user_id,
        )
        if for_update:
            query = query.with_for_update()
        return query.one_or_none()

    def get_release(self, db: Session, release_id: str, *, user_id: str) -> ManualRelease | None:
        return (
            db.query(ManualRelease)
            .filter(
                ManualRelease.id == release_id,
                ManualRelease.user_id == user_id,
            )
            .one_or_none()
        )

    def list_collection_releases(
        self,
        db: Session,
        *,
        user_id: str,
        limit: int,
        offset: int,
        include_removed: bool = False,
        artist: str | None = None,
        label: str | None = None,
        favorite: bool = False,
        folder_id: int | None = None,
    ) -> list[ManualRelease]:
        if folder_id is not None:
            return []
        return (
            self._collection_releases_query(
                db,
                user_id=user_id,
                include_removed=include_removed,
                artist=artist,
                label=label,
                favorite=favorite,
            )
            .order_by(
                ManualRelease.collection_added_at.desc().nullslast(),
                ManualRelease.artist.asc(),
                ManualRelease.title.asc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_collection_releases(
        self,
        db: Session,
        *,
        user_id: str,
        include_removed: bool = False,
        artist: str | None = None,
        label: str | None = None,
        favorite: bool = False,
        folder_id: int | None = None,
    ) -> int:
        if folder_id is not None:
            return 0
        return self._collection_releases_query(
            db,
            user_id=user_id,
            include_removed=include_removed,
            artist=artist,
            label=label,
            favorite=favorite,
        ).count()

    def search_collection_releases(
        self,
        db: Session,
        *,
        user_id: str,
        artist: str | None = None,
        title: str | None = None,
        catalog: str | None = None,
        barcode: str | None = None,
        year: int | None = None,
        limit: int,
        offset: int,
    ) -> list[ManualRelease]:
        if year is not None:
            return []

        query = db.query(ManualRelease).filter(
            ManualRelease.user_id == user_id,
            ManualRelease.in_collection.is_(True),
        )
        has_filter = False
        if artist and artist.strip():
            has_filter = True
            query = query.filter(ManualRelease.artist.ilike(f"%{artist.strip()}%"))
        if title and title.strip():
            has_filter = True
            query = query.filter(ManualRelease.title.ilike(f"%{title.strip()}%"))
        if catalog and catalog.strip():
            has_filter = True
            query = query.filter(ManualRelease.catalog_number.ilike(f"%{catalog.strip()}%"))
        if barcode and barcode.strip():
            has_filter = True
            normalized_barcode = "".join(character for character in barcode if character.isdigit())
            query = query.filter(ManualRelease.barcode.ilike(f"%{normalized_barcode or barcode.strip()}%"))
        if not has_filter:
            return []

        return query.order_by(ManualRelease.artist.asc(), ManualRelease.title.asc()).offset(offset).limit(limit).all()

    def has_favorite_collection_releases(self, db: Session, *, user_id: str) -> bool:
        return (
            db.query(ManualRelease.id)
            .filter(
                ManualRelease.user_id == user_id,
                ManualRelease.in_collection.is_(True),
                ManualRelease.is_favorite.is_(True),
            )
            .first()
            is not None
        )

    def set_favorite(
        self,
        db: Session,
        release: ManualRelease,
        *,
        is_favorite: bool,
        commit: bool = True,
    ) -> ManualRelease:
        release.is_favorite = is_favorite
        db.add(release)
        if commit:
            db.commit()
            db.refresh(release)
        else:
            db.flush()
        return release

    def deactivate_collection_membership(
        self,
        db: Session,
        release: ManualRelease,
        *,
        removed_at: datetime,
        commit: bool = True,
    ) -> ManualRelease:
        release.in_collection = False
        release.collection_removed_at = removed_at
        db.add(release)
        if commit:
            db.commit()
            db.refresh(release)
        else:
            db.flush()
        return release

    def reactivate_collection_membership(
        self,
        db: Session,
        release: ManualRelease,
        *,
        added_at: datetime,
        commit: bool = True,
    ) -> ManualRelease:
        release.in_collection = True
        release.collection_added_at = added_at
        release.collection_removed_at = None
        db.add(release)
        if commit:
            db.commit()
            db.refresh(release)
        else:
            db.flush()
        return release

    def _collection_releases_query(
        self,
        db: Session,
        *,
        user_id: str,
        include_removed: bool = False,
        artist: str | None = None,
        label: str | None = None,
        favorite: bool = False,
    ):
        query = db.query(ManualRelease).filter(ManualRelease.user_id == user_id)
        if not include_removed:
            query = query.filter(ManualRelease.in_collection.is_(True))
        if favorite:
            query = query.filter(ManualRelease.is_favorite.is_(True))
        if artist and artist.strip():
            query = query.filter(ManualRelease.artist.ilike(f"%{artist.strip()}%"))
        if label and label.strip():
            query = query.filter(func.lower(ManualRelease.label) == label.strip().lower())
        return query

    def create_draft(
        self,
        db: Session,
        *,
        user_id: str,
        form_data: ManualReleaseFormData,
        completion_state: dict | None = None,
        commit: bool = True,
    ) -> ManualReleaseDraft:
        draft = ManualReleaseDraft(
            id=str(uuid4()),
            user_id=user_id,
            form_data=form_data.model_dump(mode="json"),
            completion_state=completion_state,
        )
        db.add(draft)
        if commit:
            db.commit()
            db.refresh(draft)
        else:
            db.flush()
        return draft

    def update_draft(
        self,
        db: Session,
        draft: ManualReleaseDraft,
        *,
        form_data: ManualReleaseFormData,
        completion_state: dict | None = None,
        commit: bool = True,
    ) -> ManualReleaseDraft:
        draft.form_data = form_data.model_dump(mode="json")
        draft.completion_state = completion_state
        db.add(draft)
        if commit:
            db.commit()
            db.refresh(draft)
        else:
            db.flush()
        return draft

    def delete_draft(self, db: Session, draft: ManualReleaseDraft, *, commit: bool = True) -> None:
        db.delete(draft)
        if commit:
            db.commit()
        else:
            db.flush()

    def create_manual_release(
        self,
        db: Session,
        *,
        user_id: str,
        form_data: ManualReleaseFormData,
        draft: ManualReleaseDraft | None = None,
        commit: bool = True,
    ) -> ManualRelease:
        release = ManualRelease(
            id=str(uuid4()),
            user_id=user_id,
            artist=", ".join(form_data.artists),
            title=form_data.title or "",
            label=form_data.label or "",
            catalog_number=form_data.catalog_number,
            barcode=_normalize_barcode(form_data.barcode),
            format=form_data.format.value if form_data.format else "",
            genres=form_data.genres or None,
            styles=form_data.styles or None,
            artists=[{"name": artist} for artist in form_data.artists],
            labels=[{"name": form_data.label, "catalog_number": form_data.catalog_number}],
            identifiers={
                "catalog_number": form_data.catalog_number,
                "barcode": _normalize_barcode(form_data.barcode),
            },
            format_details={
                "format": form_data.format.value if form_data.format else None,
                "vinyl_size": form_data.vinyl_size.value if form_data.vinyl_size else None,
                "vinyl_speed": form_data.vinyl_speed.value if form_data.vinyl_speed else None,
                "vinyl_disc_count": form_data.vinyl_disc_count,
            },
            tracklist=[track.model_dump(mode="json") for track in form_data.tracklist],
            cover_storage_key=draft.cover_storage_key if draft is not None else None,
            cover_image_url=draft.cover_image_url if draft is not None else None,
            cover_thumbnail_url=draft.cover_thumbnail_url if draft is not None else None,
            cover_content_type=draft.cover_content_type if draft is not None else None,
            cover_size_bytes=draft.cover_size_bytes if draft is not None else None,
            in_collection=True,
            collection_added_at=datetime.now(UTC),
        )
        db.add(release)
        if draft is not None:
            db.delete(draft)
        if commit:
            db.commit()
            db.refresh(release)
        else:
            db.flush()
        return release


def _normalize_barcode(barcode: str | None) -> str | None:
    if barcode is None:
        return None
    normalized = "".join(character for character in barcode if character.isdigit())
    return normalized or None
