from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes.manual_releases import get_manual_release_service
from app.database.session import get_db
from app.main import app
from app.services.manual_release_policy import ManualReleaseDraftLimitExceeded
from app.services.manual_release_service import (
    CoverUploadValidationResult,
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
        self.updated_release_payloads: list[dict] = []
        self.cover_uploads: list[dict] = []
        self.deleted_release_cover_ids: list[str] = []
        self.raise_limit = False
        self.raise_not_found = False
        self.validation_error: ManualReleaseValidationError | None = None

    def list_drafts(self, _db, *, user_id: str):
        self.user_ids.append(user_id)
        return [_draft(cover_image_url="/media/manual-release-covers/test-user/draft-1/cover.jpg")]

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

    def get_release(self, _db, release_id: str, *, user_id: str):
        self.user_ids.append(user_id)
        if self.raise_not_found:
            raise ManualReleaseNotFoundError
        return _manual_release(id=release_id)

    def update_release(self, _db, release_id: str, *, user_id: str, form_data):
        self.user_ids.append(user_id)
        self.updated_release_payloads.append({"release_id": release_id, "form_data": form_data})
        if self.raise_not_found:
            raise ManualReleaseNotFoundError
        if self.validation_error is not None:
            raise self.validation_error
        return _manual_release(id=release_id, form_data=form_data.model_dump(mode="json"))

    def get_draft(self, _db, draft_id: str, *, user_id: str):
        self.user_ids.append(user_id)
        if self.raise_not_found:
            raise ManualReleaseNotFoundError
        return _draft(id=draft_id)

    def upload_cover(self, _db, *, draft_id: str, user_id: str, content_type: str | None, image_bytes: bytes):
        self.cover_uploads.append(
            {
                "draft_id": draft_id,
                "user_id": user_id,
                "content_type": content_type,
                "size_bytes": len(image_bytes),
            }
        )
        return CoverUploadValidationResult(
            content_type=content_type or "",
            size_bytes=len(image_bytes),
            cover_image_url="/media/manual-release-covers/test-user/draft-1/cover.jpg",
            cover_thumbnail_url="/media/manual-release-covers/test-user/draft-1/cover.jpg",
        )

    def upload_release_cover(self, _db, *, release_id: str, user_id: str, content_type: str | None, image_bytes: bytes):
        self.cover_uploads.append(
            {
                "release_id": release_id,
                "user_id": user_id,
                "content_type": content_type,
                "size_bytes": len(image_bytes),
            }
        )
        return CoverUploadValidationResult(
            content_type=content_type or "",
            size_bytes=len(image_bytes),
            cover_image_url="/media/manual-release-covers/test-user/manual-1/cover.jpg",
            cover_thumbnail_url="/media/manual-release-covers/test-user/manual-1/cover.jpg",
        )

    def delete_release_cover(self, _db, *, release_id: str, user_id: str) -> None:
        self.user_ids.append(user_id)
        self.deleted_release_cover_ids.append(release_id)
        if self.raise_not_found:
            raise ManualReleaseNotFoundError


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
    assert response.json()["items"][0]["year"] == 1998
    assert (
        response.json()["items"][0]["cover_thumbnail_url"] == "/media/manual-release-covers/test-user/draft-1/cover.jpg"
    )
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


def test_get_manual_release_draft_returns_full_draft() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/manual-releases/drafts/draft-1")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == "draft-1"
    assert response.json()["form_data"]["artists"] == ["Artist"]
    assert response.json()["form_data"]["title"] == "Title"
    assert response.json()["form_data"]["year"] == 1998
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


def test_get_manual_release_returns_editable_form_data() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/manual-releases/manual-1")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == "manual-1"
    assert response.json()["form_data"] == {
        "artists": ["Manual Artist"],
        "title": "Manual Title",
        "year": 1998,
        "label": "Manual Label",
        "catalog_number": "CAT-1",
        "barcode": "12345678",
        "format": "Vinyl",
        "vinyl_size": "12",
        "vinyl_speed": "33 1/3",
        "vinyl_disc_count": 1,
        "genres": ["Electronic"],
        "styles": ["Techno"],
        "tracklist": [{"title": "Track", "position": "A1", "duration": None, "credits": []}],
    }
    assert service.user_ids == ["test-user"]


def test_update_manual_release_returns_updated_detail() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    payload = {
        "form_data": {
            "artists": ["Updated Artist"],
            "title": "Updated Title",
            "label": "Updated Label",
            "format": "CD",
            "genres": ["Rock"],
            "tracklist": [{"title": "Track"}],
        }
    }
    with TestClient(app) as client:
        response = client.put("/api/v1/manual-releases/manual-1", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["form_data"]["title"] == "Updated Title"
    assert service.updated_release_payloads[0]["release_id"] == "manual-1"
    assert service.user_ids == ["test-user"]


def test_update_manual_release_returns_field_errors() -> None:
    service = StubManualReleaseService()
    service.validation_error = ManualReleaseValidationError({"title": "This field is required."})
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    payload = {"form_data": {"artists": ["Artist"], "title": "Title", "label": "Label"}}
    with TestClient(app) as client:
        response = client.put("/api/v1/manual-releases/manual-1", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "manual_release_validation_failed"
    assert response.json()["error"]["field_errors"] == {"title": "This field is required."}


def test_upload_manual_release_cover_contract_stores_after_owner_check() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-releases/manual-1/cover",
            files={"file": ("cover.jpg", b"image-bytes", "image/jpeg")},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"content_type": "image/jpeg", "size_bytes": len(b"image-bytes")}
    assert service.user_ids == ["test-user"]
    assert service.cover_uploads[-1] == {
        "release_id": "manual-1",
        "user_id": "test-user",
        "content_type": "image/jpeg",
        "size_bytes": len(b"image-bytes"),
    }


def test_delete_manual_release_cover_returns_no_content() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.delete("/api/v1/manual-releases/manual-1/cover")

    app.dependency_overrides.clear()

    assert response.status_code == 204
    assert service.deleted_release_cover_ids == ["manual-1"]
    assert service.user_ids == ["test-user"]


def test_cover_upload_contract_stores_after_owner_check() -> None:
    service = StubManualReleaseService()
    _override_db()
    app.dependency_overrides[get_manual_release_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-releases/drafts/draft-1/cover",
            files={"file": ("cover.jpg", b"image-bytes", "image/jpeg")},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"content_type": "image/jpeg", "size_bytes": len(b"image-bytes")}
    assert service.user_ids == ["test-user"]
    assert service.cover_uploads == [
        {
            "draft_id": "draft-1",
            "user_id": "test-user",
            "content_type": "image/jpeg",
            "size_bytes": len(b"image-bytes"),
        }
    ]


def _override_db() -> None:
    def _fake_db():
        yield object()

    app.dependency_overrides[get_db] = _fake_db


def _draft(
    *,
    id: str = "draft-1",
    form_data: dict | None = None,
    completion_state: dict | None = None,
    cover_image_url: str | None = None,
    cover_thumbnail_url: str | None = None,
):
    now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    return SimpleNamespace(
        id=id,
        form_data=form_data
        or {
            "artists": ["Artist"],
            "title": "Title",
            "year": 1998,
            "label": "Label",
            "format": "Vinyl",
        },
        completion_state=completion_state,
        cover_thumbnail_url=cover_thumbnail_url,
        cover_image_url=cover_image_url,
        cover_content_type=None,
        cover_size_bytes=None,
        created_at=now,
        updated_at=now,
    )


def _manual_release(
    *,
    id: str = "manual-1",
    form_data: dict | None = None,
):
    now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    data = form_data or {
        "artists": ["Manual Artist"],
        "title": "Manual Title",
        "year": 1998,
        "label": "Manual Label",
        "catalog_number": "CAT-1",
        "barcode": "12345678",
        "format": "Vinyl",
        "vinyl_size": "12",
        "vinyl_speed": "33 1/3",
        "vinyl_disc_count": 1,
        "genres": ["Electronic"],
        "styles": ["Techno"],
        "tracklist": [{"title": "Track", "position": "A1"}],
    }
    return SimpleNamespace(
        id=id,
        title=data.get("title") or "",
        artist=", ".join(data.get("artists") or []),
        year=data.get("year"),
        label=data.get("label") or "",
        catalog_number=data.get("catalog_number"),
        barcode=data.get("barcode"),
        format=data.get("format") or "",
        genres=data.get("genres"),
        styles=data.get("styles"),
        artists=[{"name": artist} for artist in data.get("artists") or []],
        format_details={
            "format": data.get("format"),
            "vinyl_size": data.get("vinyl_size"),
            "vinyl_speed": data.get("vinyl_speed"),
            "vinyl_disc_count": data.get("vinyl_disc_count"),
        },
        tracklist=data.get("tracklist") or [],
        cover_image_url="/media/manual-release-covers/test-user/manual-1/cover.jpg",
        cover_thumbnail_url="/media/manual-release-covers/test-user/manual-1/cover.jpg",
        cover_content_type="image/jpeg",
        cover_size_bytes=1234,
        in_collection=True,
        created_at=now,
        updated_at=now,
    )
