from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes.manual_releases import get_manual_release_service
from app.database.session import get_db
from app.main import app
from app.services.manual_release_policy import ManualReleaseDraftLimitExceeded
from app.services.manual_release_service import (
    ManualReleaseCoverStorageNotConfiguredError,
    ManualReleaseNotFoundError,
    ManualReleaseValidationError,
)


class StubManualReleaseService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []
        self.created_payloads: list[dict] = []
        self.updated_draft_ids: list[str] = []
        self.deleted_draft_ids: list[str] = []
        self.saved_payloads: list[dict] = []
        self.raise_limit = False
        self.raise_not_found = False
        self.validation_error: ManualReleaseValidationError | None = None

    def list_drafts(self, _db, *, user_id: str):
        self.user_ids.append(user_id)
        return [_draft()]

    def create_draft(self, _db, *, user_id: str, form_data, completion_state=None):
        self.user_ids.append(user_id)
        self.created_payloads.append({"form_data": form_data, "completion_state": completion_state})
        if self.raise_limit:
            raise ManualReleaseDraftLimitExceeded
        return _draft(form_data=form_data.model_dump(mode="json"), completion_state=completion_state)

    def update_draft(self, _db, draft_id: str, *, user_id: str, form_data, completion_state=None):
        self.user_ids.append(user_id)
        self.updated_draft_ids.append(draft_id)
        if self.raise_not_found:
            raise ManualReleaseNotFoundError
        return _draft(id=draft_id, form_data=form_data.model_dump(mode="json"), completion_state=completion_state)

    def delete_draft(self, _db, draft_id: str, *, user_id: str) -> None:
        self.user_ids.append(user_id)
        self.deleted_draft_ids.append(draft_id)
        if self.raise_not_found:
            raise ManualReleaseNotFoundError

    def save_release(self, _db, *, user_id: str, form_data=None, draft_id=None):
        self.user_ids.append(user_id)
        self.saved_payloads.append({"form_data": form_data, "draft_id": draft_id})
        if self.raise_not_found:
            raise ManualReleaseNotFoundError
        if self.validation_error is not None:
            raise self.validation_error
        return SimpleNamespace(id="manual-1", title="Manual Title", artist="Manual Artist", in_collection=True)

    def get_draft(self, _db, draft_id: str, *, user_id: str):
        self.user_ids.append(user_id)
        if self.raise_not_found:
            raise ManualReleaseNotFoundError
        return _draft(id=draft_id)

    def validate_cover_upload(self, *, content_type: str | None, size_bytes: int):
        _ = (content_type, size_bytes)
        raise ManualReleaseCoverStorageNotConfiguredError


def test_list_manual_release_drafts_returns_user_owned_summaries() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/manual-releases/drafts")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.user_ids == ["test-user"]
    assert response.json()["items"][0]["id"] == "draft-1"
    assert response.json()["remaining_slots"] == 4


def test_create_manual_release_draft_enforces_draft_cap() -> None:
    service = StubManualReleaseService()
    service.raise_limit = True
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/v1/manual-releases/drafts", json={"form_data": {"title": "Draft"}})

    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "manual_release_draft_limit_reached"
    assert service.user_ids == ["test-user"]


def test_update_manual_release_draft_returns_not_found_for_other_user() -> None:
    service = StubManualReleaseService()
    service.raise_not_found = True
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.put("/api/v1/manual-releases/drafts/other-draft", json={"form_data": {"title": "Draft"}})

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "manual_release_draft_not_found"
    assert service.updated_draft_ids == ["other-draft"]
    assert service.user_ids == ["test-user"]


def test_delete_manual_release_draft_returns_no_content() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.delete("/api/v1/manual-releases/drafts/draft-1")

    app.dependency_overrides.clear()

    assert response.status_code == 204
    assert service.deleted_draft_ids == ["draft-1"]
    assert service.user_ids == ["test-user"]


def test_save_manual_release_returns_field_errors() -> None:
    service = StubManualReleaseService()
    service.validation_error = ManualReleaseValidationError({"title": "This field is required."})
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/v1/manual-releases", json={"form_data": {"artists": ["Artist"]}})

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "manual_release_validation_failed"
    assert response.json()["error"]["field_errors"] == {"title": "This field is required."}
    assert service.user_ids == ["test-user"]


def test_save_manual_release_returns_created_manual_release() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/v1/manual-releases", json={"draft_id": "draft-1"})

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == {
        "id": "manual-1",
        "title": "Manual Title",
        "artist": "Manual Artist",
        "in_collection": True,
    }
    assert service.saved_payloads[0]["draft_id"] == "draft-1"
    assert service.user_ids == ["test-user"]


def test_cover_upload_contract_returns_storage_not_configured_after_owner_check() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-releases/drafts/draft-1/cover",
            files={"file": ("cover.jpg", b"image-bytes", "image/jpeg")},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "manual_release_cover_storage_not_configured"
    assert service.user_ids == ["test-user"]


def _override_db() -> None:
    def _fake_db():
        yield object()

    app.dependency_overrides[get_db] = _fake_db


def _draft(
    *,
    id: str = "draft-1",
    form_data: dict | None = None,
    completion_state: dict | None = None,
):
    now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    return SimpleNamespace(
        id=id,
        form_data=form_data or {"artists": ["Artist"], "title": "Title", "label": "Label", "format": "Vinyl"},
        completion_state=completion_state,
        cover_thumbnail_url=None,
        cover_image_url=None,
        cover_content_type=None,
        cover_size_bytes=None,
        created_at=now,
        updated_at=now,
    )
