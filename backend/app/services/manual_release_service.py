import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.releases import ManualRelease, ManualReleaseDraft
from app.repositories.manual_release_repository import ManualReleaseRepository
from app.schemas.manual_releases import ManualReleaseFormat, ManualReleaseFormData
from app.services.manual_release_policy import (
    ARTIST_NAME_LIMIT,
    MAX_MANUAL_RELEASE_DRAFTS,
    ManualReleaseCoverValidationError,
    ensure_manual_release_draft_capacity,
    validate_manual_release_cover_policy,
)


class ManualReleaseNotFoundError(Exception):
    """Raised when a user-owned manual release resource is missing."""


class ManualReleaseValidationError(Exception):
    """Raised when manual release form data is invalid."""

    def __init__(self, field_errors: dict[str, str]) -> None:
        self.field_errors = field_errors
        super().__init__("Manual release validation failed.")


class ManualReleaseCoverStorageNotConfiguredError(Exception):
    """Raised when upload validation passes but no cover storage backend exists."""


@dataclass(frozen=True)
class CoverUploadValidationResult:
    content_type: str
    size_bytes: int


class ManualReleaseService:
    """Business logic for user-owned manual releases and drafts."""

    def __init__(self, repository: ManualReleaseRepository | None = None) -> None:
        self.repository = repository or ManualReleaseRepository()

    def list_drafts(self, db: Session, *, user_id: str) -> list[ManualReleaseDraft]:
        return self.repository.list_drafts(db, user_id=user_id)

    def get_draft(self, db: Session, draft_id: str, *, user_id: str) -> ManualReleaseDraft:
        draft = self.repository.get_draft(db, draft_id, user_id=user_id)
        if draft is None:
            raise ManualReleaseNotFoundError
        return draft

    def remaining_draft_slots(self, db: Session, *, user_id: str) -> int:
        return max(0, MAX_MANUAL_RELEASE_DRAFTS - self.repository.count_drafts(db, user_id=user_id))

    def create_draft(
        self,
        db: Session,
        *,
        user_id: str,
        form_data: ManualReleaseFormData,
        completion_state: dict | None = None,
    ) -> ManualReleaseDraft:
        ensure_manual_release_draft_capacity(self.repository.count_drafts(db, user_id=user_id))
        return self.repository.create_draft(
            db,
            user_id=user_id,
            form_data=form_data,
            completion_state=completion_state,
        )

    def update_draft(
        self,
        db: Session,
        draft_id: str,
        *,
        user_id: str,
        form_data: ManualReleaseFormData,
        completion_state: dict | None = None,
    ) -> ManualReleaseDraft:
        draft = self.get_draft(db, draft_id, user_id=user_id)
        return self.repository.update_draft(
            db,
            draft,
            form_data=form_data,
            completion_state=completion_state,
        )

    def delete_draft(self, db: Session, draft_id: str, *, user_id: str) -> None:
        draft = self.get_draft(db, draft_id, user_id=user_id)
        self.repository.delete_draft(db, draft)

    def save_release(
        self,
        db: Session,
        *,
        user_id: str,
        form_data: ManualReleaseFormData | None = None,
        draft_id: str | None = None,
    ) -> ManualRelease:
        draft: ManualReleaseDraft | None = None
        if draft_id is not None:
            draft = self.get_draft(db, draft_id, user_id=user_id)

        if form_data is None:
            if draft is None:
                raise ManualReleaseValidationError({"form_data": "Manual release form data is required."})
            form_data = ManualReleaseFormData.model_validate(draft.form_data)

        self._validate_release_save(form_data)
        return self.repository.create_manual_release(db, user_id=user_id, form_data=form_data, draft=draft)

    def validate_cover_upload(self, *, content_type: str | None, size_bytes: int) -> CoverUploadValidationResult:
        if content_type is None:
            raise ManualReleaseCoverValidationError("Cover image content type is required.")
        validate_manual_release_cover_policy(content_type, size_bytes)
        raise ManualReleaseCoverStorageNotConfiguredError

    def _validate_release_save(self, form_data: ManualReleaseFormData) -> None:
        field_errors: dict[str, str] = {}

        valid_artists = [artist for artist in form_data.artists if artist]
        if not valid_artists:
            field_errors["artists"] = "At least one artist is required."
        elif any(len(artist) > ARTIST_NAME_LIMIT.max_length for artist in valid_artists):
            field_errors["artists"] = "Artist names must be 200 characters or fewer."

        _require_field(field_errors, "title", form_data.title)
        _require_field(field_errors, "label", form_data.label)
        _require_field(field_errors, "format", form_data.format.value if form_data.format else None)
        if form_data.format == ManualReleaseFormat.VINYL:
            _require_field(field_errors, "vinyl_size", form_data.vinyl_size.value if form_data.vinyl_size else None)
            _require_field(field_errors, "vinyl_speed", form_data.vinyl_speed.value if form_data.vinyl_speed else None)
            if form_data.vinyl_disc_count is None:
                field_errors["vinyl_disc_count"] = "Vinyl disc count is required."

        if not form_data.genres:
            field_errors["genres"] = "Genre is required."
        elif "Electronic" in form_data.genres and not form_data.styles:
            field_errors["styles"] = "Style is required when genre is Electronic."

        if not form_data.tracklist:
            field_errors["tracklist"] = "At least one track is required."
        for index, track in enumerate(form_data.tracklist):
            if not track.title:
                field_errors[f"tracklist.{index}.title"] = "Track title is required."
            if track.duration and re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", track.duration) is None:
                field_errors[f"tracklist.{index}.duration"] = "Track duration must use m:ss or h:mm:ss."
            for credit_index, credit in enumerate(track.credits):
                if not credit.name:
                    field_errors[f"tracklist.{index}.credits.{credit_index}.name"] = "Credit name is required."

        barcode = form_data.barcode
        if barcode:
            normalized_barcode = "".join(character for character in barcode if character.isdigit())
            if len(normalized_barcode) not in range(8, 15):
                field_errors["barcode"] = "Barcode must normalize to 8-14 digits."

        if field_errors:
            raise ManualReleaseValidationError(field_errors)


def _require_field(field_errors: dict[str, str], field_name: str, value: str | None) -> None:
    if not value:
        field_errors[field_name] = "This field is required."
