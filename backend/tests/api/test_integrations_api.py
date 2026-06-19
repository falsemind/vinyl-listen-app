from fastapi.testclient import TestClient

from app.api.routes.integrations import get_discogs_integration_service
from app.database.session import get_db
from app.main import app
from app.schemas.collection import CollectionSourceOfTruth
from app.schemas.integrations import DiscogsIntegrationStatusResponse
from app.services.discogs_integration_service import DiscogsTokenValidationError
from app.services.token_cipher import TokenCipherConfigurationError


class StubDiscogsIntegrationService:
    def __init__(self) -> None:
        self.status = DiscogsIntegrationStatusResponse(
            access_token_saved=False,
            source_of_truth=CollectionSourceOfTruth.APP,
            backend_identify_enabled=False,
        )
        self.save_error: Exception | None = None
        self.saved_tokens: list[str] = []
        self.seen_user_ids: list[str] = []

    def get_status(self, _db, *, user_id: str | None = None):
        self.seen_user_ids.append(user_id or "")
        return self.status

    def save_access_token(self, _db, *, access_token: str, user_id: str | None = None):
        if self.save_error is not None:
            raise self.save_error
        self.seen_user_ids.append(user_id or "")
        self.saved_tokens.append(access_token)
        self.status = DiscogsIntegrationStatusResponse(
            access_token_saved=True,
            external_user_id="123",
            external_username="alex",
            source_of_truth=CollectionSourceOfTruth.APP,
            backend_identify_enabled=True,
        )
        return self.status

    def delete_access_token(self, _db, *, user_id: str | None = None):
        self.seen_user_ids.append(user_id or "")
        self.status = DiscogsIntegrationStatusResponse(
            access_token_saved=False,
            source_of_truth=CollectionSourceOfTruth.APP,
            backend_identify_enabled=False,
        )
        return self.status


def test_get_discogs_integration_status_returns_sanitized_unsaved_state() -> None:
    service = StubDiscogsIntegrationService()
    _override_db()
    app.dependency_overrides[get_discogs_integration_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/integrations/discogs")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "provider": "DISCOGS",
        "access_token_saved": False,
        "external_user_id": None,
        "external_username": None,
        "source_of_truth": "APP",
        "backend_identify_enabled": False,
    }
    assert service.seen_user_ids == ["test-user"]


def test_save_discogs_token_returns_saved_status_without_raw_token() -> None:
    service = StubDiscogsIntegrationService()
    _override_db()
    app.dependency_overrides[get_discogs_integration_service] = lambda: service

    with TestClient(app) as client:
        response = client.put("/api/v1/integrations/discogs/token", json={"access_token": "secret-token"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "provider": "DISCOGS",
        "access_token_saved": True,
        "external_user_id": "123",
        "external_username": "alex",
        "source_of_truth": "APP",
        "backend_identify_enabled": True,
    }
    assert "secret-token" not in response.text
    assert service.saved_tokens == ["secret-token"]
    assert service.seen_user_ids == ["test-user"]


def test_save_discogs_token_returns_validation_error() -> None:
    service = StubDiscogsIntegrationService()
    service.save_error = DiscogsTokenValidationError("Discogs access token could not be validated.")
    _override_db()
    app.dependency_overrides[get_discogs_integration_service] = lambda: service

    with TestClient(app) as client:
        response = client.put("/api/v1/integrations/discogs/token", json={"access_token": "bad-token"})

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "discogs_token_invalid",
            "message": "Discogs access token could not be validated.",
        }
    }


def test_save_discogs_token_returns_storage_configuration_error() -> None:
    service = StubDiscogsIntegrationService()
    service.save_error = TokenCipherConfigurationError("missing key")
    _override_db()
    app.dependency_overrides[get_discogs_integration_service] = lambda: service

    with TestClient(app) as client:
        response = client.put("/api/v1/integrations/discogs/token", json={"access_token": "secret-token"})

    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "discogs_token_storage_not_configured",
            "message": "Discogs token storage is not configured.",
        }
    }


def test_delete_discogs_token_returns_unsaved_app_status() -> None:
    service = StubDiscogsIntegrationService()
    service.status = DiscogsIntegrationStatusResponse(
        access_token_saved=True,
        external_user_id="123",
        external_username="alex",
        source_of_truth=CollectionSourceOfTruth.DISCOGS,
        backend_identify_enabled=True,
    )
    _override_db()
    app.dependency_overrides[get_discogs_integration_service] = lambda: service

    with TestClient(app) as client:
        response = client.delete("/api/v1/integrations/discogs/token")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "provider": "DISCOGS",
        "access_token_saved": False,
        "external_user_id": None,
        "external_username": None,
        "source_of_truth": "APP",
        "backend_identify_enabled": False,
    }
    assert service.seen_user_ids == ["test-user"]


def _override_db() -> None:
    def _fake_db():
        yield object()

    app.dependency_overrides[get_db] = _fake_db
