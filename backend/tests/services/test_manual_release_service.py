from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from app.schemas.manual_releases import ManualReleaseFormData
from app.services.manual_release_cover_storage import ManualReleaseCoverStorage
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
        self.cover_updates: list[dict] = []
        self.fail_cover_update = False
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

    def update_draft_cover(
        self,
        _db,
        draft,
        *,
        cover_storage_key: str,
        cover_image_url: str,
        cover_thumbnail_url: str,
        cover_content_type: str,
        cover_size_bytes: int,
    ):
        if self.fail_cover_update:
            raise RuntimeError("cover update failed")
        self.cover_updates.append(
            {
                "draft_id": draft.id,
                "cover_storage_key": cover_storage_key,
                "cover_image_url": cover_image_url,
                "cover_thumbnail_url": cover_thumbnail_url,
                "cover_content_type": cover_content_type,
                "cover_size_bytes": cover_size_bytes,
            }
        )
        return draft


def test_create_draft_enforces_user_draft_limit() -> None:
    repository = FakeManualReleaseRepository()
    repository.draft_count = 5
    service = ManualReleaseService(repository)

    with pytest.raises(ManualReleaseDraftLimitExceeded):
        service.create_draft(object(), user_id="user-1", form_data=ManualReleaseFormData(title="Partial"))


def test_create_draft_serializes_capacity_check_before_counting(monkeypatch) -> None:
    repository = FakeManualReleaseRepository()
    service = ManualReleaseService(repository)
    fake_repository = repository

    def record_account_data_lock(_db, *, user_id: str, repository=None) -> None:
        _ = repository
        fake_repository.operation_log.append(f"account-lock:{user_id}")

    monkeypatch.setattr(
        "app.services.manual_release_service.lock_account_data_mutation",
        record_account_data_lock,
    )

    service.create_draft(object(), user_id="user-1", form_data=ManualReleaseFormData(title="Partial"))

    assert repository.operation_log == [
        "account-lock:user-1",
        "lock:user-1",
        "count:user-1",
        "create:user-1",
    ]


def test_upload_cover_stores_file_and_updates_draft_metadata(tmp_path) -> None:
    repository = FakeManualReleaseRepository()
    service = ManualReleaseService(
        repository,
        cover_storage=ManualReleaseCoverStorage(
            root_dir=tmp_path,
            public_url_prefix="/media/manual-release-covers",
        ),
    )
    image_bytes = _cover_image_bytes(width=120, height=100)

    result = service.upload_cover(
        object(),
        draft_id="draft-1",
        user_id="user-1",
        content_type=" IMAGE/PNG ",
        image_bytes=image_bytes,
    )

    stored_files = list((tmp_path / "user-1" / "draft-1").glob("cover-*.png"))
    assert len(stored_files) == 1
    stored_file = stored_files[0]
    assert stored_file.read_bytes() == image_bytes
    storage_key = f"manual-release-covers/user-1/draft-1/{stored_file.name}"
    image_url = f"/media/manual-release-covers/user-1/draft-1/{stored_file.name}"
    assert result.content_type == "image/png"
    assert result.size_bytes == len(image_bytes)
    assert result.cover_image_url == image_url
    assert repository.get_draft_calls == [
        {
            "draft_id": "draft-1",
            "user_id": "user-1",
            "for_update": True,
        }
    ]
    assert repository.cover_updates == [
        {
            "draft_id": "draft-1",
            "cover_storage_key": storage_key,
            "cover_image_url": image_url,
            "cover_thumbnail_url": image_url,
            "cover_content_type": "image/png",
            "cover_size_bytes": len(image_bytes),
        }
    ]


def test_upload_cover_cleans_old_cover_after_draft_metadata_update(tmp_path) -> None:
    repository = FakeManualReleaseRepository()
    service = ManualReleaseService(
        repository,
        cover_storage=ManualReleaseCoverStorage(
            root_dir=tmp_path,
            public_url_prefix="/media/manual-release-covers",
        ),
    )
    old_cover = tmp_path / "user-1" / "draft-1" / "cover.png"
    old_cover.parent.mkdir(parents=True)
    old_cover.write_bytes(b"old")

    service.upload_cover(
        object(),
        draft_id="draft-1",
        user_id="user-1",
        content_type="image/png",
        image_bytes=_cover_image_bytes(width=120, height=100),
    )

    assert not old_cover.exists()
    assert len(list(old_cover.parent.glob("cover-*.png"))) == 1


def test_upload_cover_deletes_new_file_when_draft_metadata_update_fails(tmp_path) -> None:
    repository = FakeManualReleaseRepository()
    repository.fail_cover_update = True
    service = ManualReleaseService(
        repository,
        cover_storage=ManualReleaseCoverStorage(
            root_dir=tmp_path,
            public_url_prefix="/media/manual-release-covers",
        ),
    )

    with pytest.raises(RuntimeError, match="cover update failed"):
        service.upload_cover(
            object(),
            draft_id="draft-1",
            user_id="user-1",
            content_type="image/png",
            image_bytes=_cover_image_bytes(width=120, height=100),
        )

    cover_dir = tmp_path / "user-1" / "draft-1"
    assert list(cover_dir.glob("cover-*.png")) == []
    assert list(cover_dir.glob(".cover-*.tmp")) == []


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


def test_save_release_requires_track_position_for_vinyl() -> None:
    service = ManualReleaseService(FakeManualReleaseRepository())
    form_data = ManualReleaseFormData(
        artists=["Artist"],
        title="Title",
        label="Label",
        format="Vinyl",
        vinyl_size="12",
        vinyl_speed="33 1/3",
        vinyl_disc_count=1,
        genres=["Electronic"],
        styles=["Techno"],
        tracklist=[{"title": "Track"}],
    )

    with pytest.raises(ManualReleaseValidationError) as exc_info:
        service.save_release(object(), user_id="user-1", form_data=form_data)

    assert exc_info.value.field_errors["tracklist.0.position"] == "Track position is required for vinyl releases."


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
        tracklist=[{"title": "A1", "position": "A1", "duration": "6:30"}],
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


def _cover_image_bytes(*, width: int, height: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color=(32, 96, 64)).save(output, format="PNG")
    return output.getvalue()
