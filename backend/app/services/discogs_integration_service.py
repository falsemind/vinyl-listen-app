from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.repositories.collection_settings_repository import CollectionSettingsRepository
from app.repositories.provider_integration_repository import ProviderIntegrationRepository
from app.schemas.integrations import DiscogsIntegrationStatusResponse
from app.services.discogs_service import (
    DiscogsApiConfig,
    DiscogsClient,
    DiscogsClientError,
    DiscogsConfigurationError,
    DiscogsRateLimiter,
    DiscogsService,
)
from app.services.token_cipher import TokenCipher, TokenCipherConfigurationError, TokenCipherError

UNAUTHENTICATED_DISCOGS_RATE_LIMIT_PER_MINUTE = 25


class DiscogsTokenValidationError(Exception):
    """Raised when a Discogs token cannot be validated."""


@dataclass(frozen=True)
class DiscogsIdentity:
    user_id: str
    username: str


@dataclass(frozen=True)
class SavedDiscogsCredentials:
    access_token: str
    username: str
    external_user_id: str


class DiscogsIdentityClientProtocol(Protocol):
    def fetch_identity(self, access_token: str) -> DiscogsIdentity:
        """Return the Discogs identity for a personal access token."""


class DiscogsIdentityClient:
    """Client for Discogs token identity validation."""

    def fetch_identity(self, access_token: str) -> DiscogsIdentity:
        client = DiscogsClient(config=DiscogsApiConfig.from_token(access_token))
        try:
            payload = client.get("/oauth/identity")
        except DiscogsClientError as error:
            raise DiscogsTokenValidationError("Discogs access token could not be validated.") from error

        return _identity_from_payload(payload)


class DiscogsIntegrationService:
    """Coordinate Discogs token validation, storage, and sanitized status."""

    def __init__(
        self,
        *,
        integration_repository: ProviderIntegrationRepository | None = None,
        collection_settings_repository: CollectionSettingsRepository | None = None,
        identity_client: DiscogsIdentityClientProtocol | None = None,
        token_cipher: TokenCipher | None = None,
    ) -> None:
        self._integration_repository = integration_repository or ProviderIntegrationRepository()
        self._collection_settings_repository = collection_settings_repository or CollectionSettingsRepository()
        self._identity_client = identity_client or DiscogsIdentityClient()
        self._token_cipher = token_cipher

    def get_status(self, db: Session, *, user_id: str | None = None) -> DiscogsIntegrationStatusResponse:
        integration = self._integration_repository.get_discogs(db, user_id=user_id)
        source_of_truth = self._collection_settings_repository.get_source_of_truth(db)
        access_token_saved = bool(
            integration
            and integration.is_active
            and integration.access_token_ciphertext
            and integration.external_username
            and integration.external_user_id
        )

        return DiscogsIntegrationStatusResponse(
            access_token_saved=access_token_saved,
            external_user_id=integration.external_user_id if access_token_saved and integration else None,
            external_username=integration.external_username if access_token_saved and integration else None,
            source_of_truth=source_of_truth,
            backend_identify_enabled=access_token_saved,
        )

    def save_access_token(
        self,
        db: Session,
        *,
        access_token: str,
        user_id: str | None = None,
    ) -> DiscogsIntegrationStatusResponse:
        normalized_token = access_token.strip()
        if not normalized_token:
            raise DiscogsTokenValidationError("Discogs access token is required.")

        identity = self._identity_client.fetch_identity(normalized_token)
        ciphertext = self._get_token_cipher().encrypt(normalized_token)
        self._integration_repository.upsert_discogs_token(
            db,
            access_token_ciphertext=ciphertext,
            external_user_id=identity.user_id,
            external_username=identity.username,
            user_id=user_id,
        )
        return self.get_status(db, user_id=user_id)

    def get_saved_credentials(self, db: Session, *, user_id: str | None = None) -> SavedDiscogsCredentials:
        integration = self._integration_repository.get_discogs(db, user_id=user_id)
        if not (
            integration
            and integration.is_active
            and integration.access_token_ciphertext
            and integration.external_username
            and integration.external_user_id
        ):
            raise DiscogsConfigurationError("Discogs token is not configured.")

        try:
            access_token = self._get_token_cipher().decrypt(integration.access_token_ciphertext)
        except (TokenCipherConfigurationError, TokenCipherError) as error:
            raise DiscogsConfigurationError("Discogs token storage is not configured.") from error

        return SavedDiscogsCredentials(
            access_token=access_token,
            username=integration.external_username,
            external_user_id=integration.external_user_id,
        )

    def build_discogs_service(self, db: Session, *, user_id: str | None = None) -> "DiscogsService":
        credentials = self.get_saved_credentials(db, user_id=user_id)
        return DiscogsService(
            client=DiscogsClient(config=DiscogsApiConfig.from_token(credentials.access_token)),
        )

    def build_unauthenticated_discogs_service(self) -> "DiscogsService":
        return DiscogsService(
            client=DiscogsClient(
                config=DiscogsApiConfig.unauthenticated(),
                rate_limiter=DiscogsRateLimiter(UNAUTHENTICATED_DISCOGS_RATE_LIMIT_PER_MINUTE),
            ),
        )

    def _get_token_cipher(self) -> TokenCipher:
        if self._token_cipher is not None:
            return self._token_cipher

        self._token_cipher = TokenCipher.from_settings()
        return self._token_cipher


def _identity_from_payload(payload: dict[str, Any]) -> DiscogsIdentity:
    user_id = payload.get("id")
    username = payload.get("username")

    if not isinstance(username, str) or not username.strip():
        raise DiscogsTokenValidationError("Discogs identity response is missing username.")

    if isinstance(user_id, int):
        normalized_user_id = str(user_id)
    elif isinstance(user_id, str) and user_id.strip():
        normalized_user_id = user_id.strip()
    else:
        raise DiscogsTokenValidationError("Discogs identity response is missing user id.")

    return DiscogsIdentity(user_id=normalized_user_id, username=username.strip())


__all__ = [
    "DiscogsIdentity",
    "DiscogsIdentityClient",
    "DiscogsIntegrationService",
    "DiscogsTokenValidationError",
    "SavedDiscogsCredentials",
    "TokenCipherConfigurationError",
]
