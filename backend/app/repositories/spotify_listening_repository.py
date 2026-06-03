from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.spotify_listening import SpotifyListeningEvent, SpotifyListeningImportBatch


class SpotifyListeningRepository:
    @staticmethod
    def create_import_batch(db: Session, source_paths: Sequence[str]) -> SpotifyListeningImportBatch:
        batch = SpotifyListeningImportBatch(
            source_paths=list(source_paths),
            status="running",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def get_existing_event_keys(db: Session, event_keys: Sequence[str]) -> set[str]:
        if not event_keys:
            return set()

        rows = db.query(SpotifyListeningEvent.event_key).filter(SpotifyListeningEvent.event_key.in_(event_keys)).all()
        return {row[0] for row in rows}

    @staticmethod
    def add_new_events(db: Session, events: Sequence[SpotifyListeningEvent]) -> tuple[int, int]:
        existing_keys = SpotifyListeningRepository.get_existing_event_keys(db, [event.event_key for event in events])
        new_events = [event for event in events if event.event_key not in existing_keys]

        if new_events:
            db.add_all(new_events)
            db.flush()

        return len(new_events), len(events) - len(new_events)

    @staticmethod
    def mark_completed(
        db: Session,
        batch_id: str,
        *,
        total_items: int,
        imported_count: int,
        duplicate_count: int,
        skipped_count: int,
        error_count: int,
        error_summary: Sequence[str],
    ) -> SpotifyListeningImportBatch:
        batch = db.get(SpotifyListeningImportBatch, batch_id)
        if batch is None:
            raise ValueError(f"Spotify import batch not found: {batch_id}")

        batch.status = "completed"
        batch.total_items = total_items
        batch.imported_count = imported_count
        batch.duplicate_count = duplicate_count
        batch.skipped_count = skipped_count
        batch.error_count = error_count
        batch.error_summary = list(error_summary) or None
        batch.completed_at = datetime.now(UTC)
        db.add(batch)
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def mark_failed(
        db: Session,
        batch_id: str,
        *,
        total_items: int,
        imported_count: int,
        duplicate_count: int,
        skipped_count: int,
        error_count: int,
        error_summary: Sequence[str],
    ) -> SpotifyListeningImportBatch:
        batch = db.get(SpotifyListeningImportBatch, batch_id)
        if batch is None:
            raise ValueError(f"Spotify import batch not found: {batch_id}")

        batch.status = "failed"
        batch.total_items = total_items
        batch.imported_count = imported_count
        batch.duplicate_count = duplicate_count
        batch.skipped_count = skipped_count
        batch.error_count = error_count
        batch.error_summary = list(error_summary) or None
        batch.completed_at = datetime.now(UTC)
        db.add(batch)
        db.commit()
        db.refresh(batch)
        return batch
