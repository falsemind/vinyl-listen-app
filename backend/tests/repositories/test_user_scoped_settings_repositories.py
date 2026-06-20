from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.collection_settings import CollectionSettings
from app.models.provider_integration import ProviderIntegration
from app.repositories.collection_settings_repository import CollectionSettingsRepository
from app.repositories.provider_integration_repository import ProviderIntegrationRepository
from app.schemas.collection import CollectionSourceOfTruth


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    CollectionSettings.__table__.create(engine)
    ProviderIntegration.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        ProviderIntegration.__table__.drop(engine)
        CollectionSettings.__table__.drop(engine)


def test_collection_settings_are_scoped_by_user(db_session: Session) -> None:
    repository = CollectionSettingsRepository()

    repository.set_source_of_truth(
        db_session,
        CollectionSourceOfTruth.DISCOGS,
        user_id="user-a",
    )

    user_a_settings = repository.get_or_create(db_session, user_id="user-a")
    user_b_settings = repository.get_or_create(db_session, user_id="user-b")

    assert user_a_settings.source_of_truth == CollectionSourceOfTruth.DISCOGS.value
    assert user_b_settings.source_of_truth == CollectionSourceOfTruth.APP.value
    assert user_a_settings.user_id == "user-a"
    assert user_b_settings.user_id == "user-b"


def test_provider_integrations_are_scoped_by_user(db_session: Session) -> None:
    repository = ProviderIntegrationRepository()

    repository.upsert_discogs_token(
        db_session,
        access_token_ciphertext="cipher-a",
        external_user_id="discogs-a",
        external_username="alex",
        user_id="user-a",
    )
    repository.upsert_discogs_token(
        db_session,
        access_token_ciphertext="cipher-b",
        external_user_id="discogs-b",
        external_username="sam",
        user_id="user-b",
    )
    repository.delete_discogs_token(db_session, user_id="user-a")

    user_a_integration = repository.get_discogs(db_session, user_id="user-a")
    user_b_integration = repository.get_discogs(db_session, user_id="user-b")

    assert user_a_integration is not None
    assert user_a_integration.is_active is False
    assert user_a_integration.access_token_ciphertext is None
    assert user_b_integration is not None
    assert user_b_integration.is_active is True
    assert user_b_integration.access_token_ciphertext == "cipher-b"
