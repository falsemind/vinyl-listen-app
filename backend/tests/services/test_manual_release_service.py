from types import SimpleNamespace

import pytest

from app.schemas.manual_releases import ManualReleaseFormData
from app.services.manual_release_policy import ManualReleaseDraftLimitExceeded
from app.services.manual_release_service import ManualReleaseService, ManualReleaseValidationError


class FakeManualReleaseRepository:
    def __init__(self) -> None:
        self.draft_count = 0
        self.created_draft_user_ids: list[str] = []
        self.created_release_user_ids: list[str] = []
        self.saved_form_data: ManualReleaseFormData | None = None

    def count_drafts(self, _db, *, user_id: str) -> int:
        _ = user_id
        return self.draft_count

    def create_draft(self, _db, *, user_id: str, form_data, completion_state=None):
        _ = completion_state
        self.created_draft_user_ids.append(user_id)
        return SimpleNamespace(id="draft-1", user_id=user_id, form_data=form_data.model_dump(mode="json"))

    def create_manual_release(self, _db, *, user_id: str, form_data, draft=None):
        _ = draft
        self.created_release_user_ids.append(user_id)
        self.saved_form_data = form_data
        return SimpleNamespace(id="manual-1", user_id=user_id, title=form_data.title)


def test_create_draft_enforces_user_draft_limit() -> None:
    repository = FakeManualReleaseRepository()
    repository.draft_count = 5
    service = ManualReleaseService(repository)

    with pytest.raises(ManualReleaseDraftLimitExceeded):
        service.create_draft(object(), user_id="user-1", form_data=ManualReleaseFormData(title="Partial"))


def test_save_release_requires_complete_form_data() -> None:
    service = ManualReleaseService(FakeManualReleaseRepository())

    with pytest.raises(ManualReleaseValidationError) as exc_info:
        service.save_release(object(), user_id="user-1", form_data=ManualReleaseFormData(artists=["Artist"]))

    assert exc_info.value.field_errors["title"] == "This field is required."
    assert exc_info.value.field_errors["label"] == "This field is required."


def test_save_release_accepts_complete_vinyl_form_data() -> None:
    repository = FakeManualReleaseRepository()
    service = ManualReleaseService(repository)
    form_data = ManualReleaseFormData(
        artists=["Artist"],
        title="Title",
        label="Label",
        format="Vinyl",
        vinyl_size="12",
        vinyl_speed="33 1/3",
        vinyl_disc_count=2,
        genres=["Electronic"],
        styles=["Techno"],
        tracklist=[{"title": "A1", "duration": "6:30"}],
    )

    release = service.save_release(object(), user_id="user-1", form_data=form_data)

    assert release.id == "manual-1"
    assert repository.created_release_user_ids == ["user-1"]
    assert repository.saved_form_data == form_data


def test_save_release_returns_field_error_for_bad_duration() -> None:
    service = ManualReleaseService(FakeManualReleaseRepository())
    form_data = ManualReleaseFormData(
        artists=["Artist"],
        title="Title",
        label="Label",
        format="CD",
        genres=["Rock"],
        tracklist=[{"title": "Track", "duration": "bad"}],
    )

    with pytest.raises(ManualReleaseValidationError) as exc_info:
        service.save_release(object(), user_id="user-1", form_data=form_data)

    assert exc_info.value.field_errors == {"tracklist.0.duration": "Track duration must use m:ss or h:mm:ss."}
