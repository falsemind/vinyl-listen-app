from sqlalchemy.orm import Session

from app.models.collection_settings import CollectionSettings
from app.schemas.collection import CollectionSourceOfTruth


class CollectionSettingsRepository:
    """Repository for app-level collection settings."""

    SETTINGS_ROW_ID = 1

    def get_or_create(self, db: Session, *, commit: bool = True) -> CollectionSettings:
        settings = db.query(CollectionSettings).filter(CollectionSettings.id == self.SETTINGS_ROW_ID).one_or_none()
        if settings is not None:
            return settings

        settings = CollectionSettings(
            id=self.SETTINGS_ROW_ID,
            source_of_truth=CollectionSourceOfTruth.APP.value,
        )
        db.add(settings)
        if commit:
            db.commit()
            db.refresh(settings)
        else:
            db.flush()
        return settings

    def get_source_of_truth(self, db: Session) -> CollectionSourceOfTruth:
        settings = self.get_or_create(db)
        return CollectionSourceOfTruth(settings.source_of_truth)

    def set_source_of_truth(
        self,
        db: Session,
        source_of_truth: CollectionSourceOfTruth,
        *,
        commit: bool = True,
    ) -> CollectionSettings:
        settings = self.get_or_create(db, commit=False)
        settings.source_of_truth = source_of_truth.value
        db.add(settings)
        if commit:
            db.commit()
            db.refresh(settings)
        else:
            db.flush()
        return settings
