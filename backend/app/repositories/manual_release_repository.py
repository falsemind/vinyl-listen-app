from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.releases import ManualRelease, ManualReleaseDraft
from app.schemas.manual_releases import ManualReleaseFormData


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

    def get_draft(self, db: Session, draft_id: str, *, user_id: str) -> ManualReleaseDraft | None:
        return (
            db.query(ManualReleaseDraft)
            .filter(ManualReleaseDraft.id == draft_id, ManualReleaseDraft.user_id == user_id)
            .one_or_none()
        )

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
