from sqlalchemy.orm import Session

from app.models.provider_integration import ProviderIntegration


class ProviderIntegrationRepository:
    """Repository for external provider integration settings."""

    DISCOGS_PROVIDER = "DISCOGS"

    def get_discogs(self, db: Session, *, user_id: str | None = None) -> ProviderIntegration | None:
        if user_id is None:
            user_filter = ProviderIntegration.user_id.is_(None)
        else:
            user_filter = ProviderIntegration.user_id == user_id

        return (
            db.query(ProviderIntegration)
            .filter(ProviderIntegration.provider == self.DISCOGS_PROVIDER)
            .filter(user_filter)
            .order_by(ProviderIntegration.id.asc())
            .one_or_none()
        )

    def upsert_discogs_token(
        self,
        db: Session,
        *,
        access_token_ciphertext: str,
        external_user_id: str,
        external_username: str,
        user_id: str | None = None,
        commit: bool = True,
    ) -> ProviderIntegration:
        integration = self.get_discogs(db, user_id=user_id)
        if integration is None:
            integration = ProviderIntegration(
                provider=self.DISCOGS_PROVIDER,
                user_id=user_id,
            )

        integration.access_token_ciphertext = access_token_ciphertext
        integration.external_user_id = external_user_id
        integration.external_username = external_username
        integration.is_active = True
        db.add(integration)

        if commit:
            db.commit()
            db.refresh(integration)
        else:
            db.flush()

        return integration
