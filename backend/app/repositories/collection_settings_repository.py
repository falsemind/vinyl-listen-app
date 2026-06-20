from sqlalchemy.orm import Session

from app.models.collection_settings import CollectionSettings
from app.schemas.collection import CollectionSourceOfTruth


class CollectionSettingsRepository:
    """Repository for user-owned collection settings."""

    SETTINGS_ROW_ID = 1

    def get_or_create(
        self,
        db: Session,
        *,
        user_id: str | None = None,
        commit: bool = True,
    ) -> CollectionSettings:
        user_filter = CollectionSettings.user_id.is_(None) if user_id is None else CollectionSettings.user_id == user_id

        settings = db.query(CollectionSettings).filter(user_filter).one_or_none()
        if settings is not None:
            return settings

        settings = CollectionSettings(
            id=self.SETTINGS_ROW_ID if user_id is None else None,
            user_id=user_id,
            source_of_truth=CollectionSourceOfTruth.APP.value,
        )
        db.add(settings)
        if commit:
            db.commit()
            db.refresh(settings)
        else:
            db.flush()
        return settings

    def get_source_of_truth(self, db: Session, *, user_id: str | None = None) -> CollectionSourceOfTruth:
        settings = self.get_or_create(db, user_id=user_id)
        return CollectionSourceOfTruth(settings.source_of_truth)

    def set_source_of_truth(
        self,
        db: Session,
        source_of_truth: CollectionSourceOfTruth,
        *,
        user_id: str | None = None,
        commit: bool = True,
    ) -> CollectionSettings:
        settings = self.get_or_create(db, user_id=user_id, commit=False)
        settings.source_of_truth = source_of_truth.value
        db.add(settings)
        if commit:
            db.commit()
            db.refresh(settings)
        else:
            db.flush()
        return settings
