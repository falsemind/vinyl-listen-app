from types import SimpleNamespace

import pytest

from app.schemas.collection import CollectionSourceOfTruth
from app.services.discogs_integration_service import (
    DiscogsIdentity,
    DiscogsIntegrationService,
    DiscogsTokenValidationError,
)


class FakeIntegrationRepository:
    def __init__(self, integration=None) -> None:
        self.integration = integration
        self.saved_tokens: list[dict] = []

    def get_discogs(self, _db, *, user_id: str | None = None):
        _ = user_id
        return self.integration

    def upsert_discogs_token(
        self,
        _db,
        *,
        access_token_ciphertext: str,
        external_user_id: str,
        external_username: str,
        user_id: str | None = None,
    ):
        self.saved_tokens.append(
            {
                "access_token_ciphertext": access_token_ciphertext,
                "external_user_id": external_user_id,
                "external_username": external_username,
                "user_id": user_id,
            }
        )
        self.integration = SimpleNamespace(
            is_active=True,
            access_token_ciphertext=access_token_ciphertext,
            external_user_id=external_user_id,
            external_username=external_username,
        )
        return self.integration


class FakeCollectionSettingsRepository:
    def __init__(self, source_of_truth: CollectionSourceOfTruth = CollectionSourceOfTruth.APP) -> None:
        self.source_of_truth = source_of_truth

    def get_source_of_truth(self, _db) -> CollectionSourceOfTruth:
        return self.source_of_truth


class FakeIdentityClient:
    def __init__(self, identity: DiscogsIdentity | None = None, error: Exception | None = None) -> None:
        self.identity = identity or DiscogsIdentity(user_id="123", username="alex")
        self.error = error
        self.tokens: list[str] = []

    def fetch_identity(self, access_token: str) -> DiscogsIdentity:
        self.tokens.append(access_token)
        if self.error is not None:
            raise self.error
        return self.identity


class FakeTokenCipher:
    def encrypt(self, plaintext: str) -> str:
        return f"encrypted:{plaintext[::-1]}"

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext.removeprefix("encrypted:")[::-1]


def test_get_status_returns_unsaved_state() -> None:
    service = DiscogsIntegrationService(
        integration_repository=FakeIntegrationRepository(),
        collection_settings_repository=FakeCollectionSettingsRepository(),
        identity_client=FakeIdentityClient(),
        token_cipher=FakeTokenCipher(),
    )

    status = service.get_status(object())

    assert status.access_token_saved is False
    assert status.external_user_id is None
    assert status.external_username is None
    assert status.source_of_truth == CollectionSourceOfTruth.APP
    assert status.backend_identify_enabled is False


def test_save_access_token_validates_identity_and_stores_encrypted_token() -> None:
    repository = FakeIntegrationRepository()
    identity_client = FakeIdentityClient(DiscogsIdentity(user_id="456", username="discogs-user"))
    service = DiscogsIntegrationService(
        integration_repository=repository,
        collection_settings_repository=FakeCollectionSettingsRepository(CollectionSourceOfTruth.DISCOGS),
        identity_client=identity_client,
        token_cipher=FakeTokenCipher(),
    )

    status = service.save_access_token(object(), access_token=" secret-token ")

    assert identity_client.tokens == ["secret-token"]
    assert repository.saved_tokens == [
        {
            "access_token_ciphertext": "encrypted:nekot-terces",
            "external_user_id": "456",
            "external_username": "discogs-user",
            "user_id": None,
        }
    ]
    assert "secret-token" not in repository.saved_tokens[0]["access_token_ciphertext"]
    assert status.access_token_saved is True
    assert status.external_user_id == "456"
    assert status.external_username == "discogs-user"
    assert status.source_of_truth == CollectionSourceOfTruth.DISCOGS
    assert status.backend_identify_enabled is True


def test_save_access_token_does_not_store_invalid_token() -> None:
    repository = FakeIntegrationRepository()
    service = DiscogsIntegrationService(
        integration_repository=repository,
        collection_settings_repository=FakeCollectionSettingsRepository(),
        identity_client=FakeIdentityClient(error=DiscogsTokenValidationError("invalid token")),
        token_cipher=FakeTokenCipher(),
    )

    with pytest.raises(DiscogsTokenValidationError):
        service.save_access_token(object(), access_token="bad-token")

    assert repository.saved_tokens == []


def test_get_saved_credentials_decrypts_saved_token() -> None:
    service = DiscogsIntegrationService(
        integration_repository=FakeIntegrationRepository(
            integration=SimpleNamespace(
                is_active=True,
                access_token_ciphertext="encrypted:nekot-terces",
                external_user_id="456",
                external_username="discogs-user",
            )
        ),
        collection_settings_repository=FakeCollectionSettingsRepository(),
        identity_client=FakeIdentityClient(),
        token_cipher=FakeTokenCipher(),
    )

    credentials = service.get_saved_credentials(object())

    assert credentials.access_token == "secret-token"
    assert credentials.username == "discogs-user"
    assert credentials.external_user_id == "456"
