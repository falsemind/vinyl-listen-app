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
        self.get_draft_calls: list[dict] = []
        self.operation_log: list[str] = []
        self.saved_form_data: ManualReleaseFormData | None = None
        self.draft_form_data = ManualReleaseFormData(
            artists=["Draft Artist"],
            title="Draft Title",
            label="Draft Label",
            format="CD",
            genres=["Rock"],
            tracklist=[{"title": "Draft Track"}],
        )

    def lock_draft_capacity_for_user(self, _db, *, user_id: str) -> None:
        self.operation_log.append(f"lock:{user_id}")

    def count_drafts(self, _db, *, user_id: str) -> int:
        self.operation_log.append(f"count:{user_id}")
        return self.draft_count

    def get_draft(self, _db, draft_id: str, *, user_id: str, for_update: bool = False):
        self.get_draft_calls.append(
            {
                "draft_id": draft_id,
                "user_id": user_id,
                "for_update": for_update,
            }
        )
        return SimpleNamespace(
            id=draft_id,
            user_id=user_id,
            form_data=self.draft_form_data.model_dump(mode="json"),
        )

    def create_draft(self, _db, *, user_id: str, form_data, completion_state=None):
        _ = completion_state
        self.operation_log.append(f"create:{user_id}")
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


def test_create_draft_serializes_capacity_check_before_counting() -> None:
    repository = FakeManualReleaseRepository()
    service = ManualReleaseService(repository)

    service.create_draft(object(), user_id="user-1", form_data=ManualReleaseFormData(title="Partial"))

    assert repository.operation_log == ["lock:user-1", "count:user-1", "create:user-1"]


def test_save_release_requires_complete_form_data() -> None:
    service = ManualReleaseService(FakeManualReleaseRepository())

    with pytest.raises(ManualReleaseValidationError) as exc_info:
        service.save_release(object(), user_id="user-1", form_data=ManualReleaseFormData(artists=["Artist"]))

    assert exc_info.value.field_errors["title"] == "This field is required."
    assert exc_info.value.field_errors["label"] == "This field is required."


def test_save_release_rejects_whitespace_only_artist() -> None:
    service = ManualReleaseService(FakeManualReleaseRepository())
    form_data = ManualReleaseFormData(
        artists=["   "],
        title="Title",
        label="Label",
        format="CD",
        genres=["Rock"],
        tracklist=[{"title": "Track"}],
    )

    with pytest.raises(ManualReleaseValidationError) as exc_info:
        service.save_release(object(), user_id="user-1", form_data=form_data)

    assert exc_info.value.field_errors["artists"] == "At least one artist is required."


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


def test_save_release_locks_draft_before_consuming_it() -> None:
    repository = FakeManualReleaseRepository()
    service = ManualReleaseService(repository)

    release = service.save_release(object(), user_id="user-1", draft_id="draft-1")

    assert release.id == "manual-1"
    assert repository.get_draft_calls == [
        {
            "draft_id": "draft-1",
            "user_id": "user-1",
            "for_update": True,
        }
    ]
    assert repository.saved_form_data == repository.draft_form_data


def test_save_release_normalizes_list_string_fields_for_electronic_style_validation() -> None:
    repository = FakeManualReleaseRepository()
    service = ManualReleaseService(repository)
    form_data = ManualReleaseFormData(
        artists=[" Artist ", "   "],
        title="Title",
        label="Label",
        format="CD",
        genres=[" Electronic "],
        styles=[" Techno "],
        tracklist=[{"title": "Track"}],
    )

    service.save_release(object(), user_id="user-1", form_data=form_data)

    assert repository.saved_form_data is not None
    assert repository.saved_form_data.artists == ["Artist"]
    assert repository.saved_form_data.genres == ["Electronic"]
    assert repository.saved_form_data.styles == ["Techno"]


def test_save_release_requires_style_for_normalized_electronic_genre() -> None:
    service = ManualReleaseService(FakeManualReleaseRepository())
    form_data = ManualReleaseFormData(
        artists=["Artist"],
        title="Title",
        label="Label",
        format="CD",
        genres=[" Electronic "],
        styles=["   "],
        tracklist=[{"title": "Track"}],
    )

    with pytest.raises(ManualReleaseValidationError) as exc_info:
        service.save_release(object(), user_id="user-1", form_data=form_data)

    assert exc_info.value.field_errors["styles"] == "Style is required when genre is Electronic."


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
