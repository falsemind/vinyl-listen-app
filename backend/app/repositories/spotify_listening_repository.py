from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.spotify_listening import (
    SpotifyAlbumStats,
    SpotifyArtistStats,
    SpotifyHourlyStats,
    SpotifyListeningEvent,
    SpotifyListeningImportBatch,
    SpotifyMonthlyArtistStats,
    SpotifySkipStats,
    SpotifyTrackStats,
    SpotifyVinylArtistMatch,
    SpotifyVinylReleaseMatch,
)


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
    def clear_rollups_and_matches(db: Session) -> None:
        for model in (
            SpotifyVinylReleaseMatch,
            SpotifyVinylArtistMatch,
            SpotifySkipStats,
            SpotifyMonthlyArtistStats,
            SpotifyHourlyStats,
            SpotifyTrackStats,
            SpotifyAlbumStats,
            SpotifyArtistStats,
        ):
            db.query(model).delete()

    @staticmethod
    def add_rollups_and_matches(
        db: Session,
        *,
        artist_stats: Sequence[SpotifyArtistStats],
        album_stats: Sequence[SpotifyAlbumStats],
        track_stats: Sequence[SpotifyTrackStats],
        hourly_stats: Sequence[SpotifyHourlyStats],
        monthly_artist_stats: Sequence[SpotifyMonthlyArtistStats],
        skip_stats: Sequence[SpotifySkipStats],
        artist_matches: Sequence[SpotifyVinylArtistMatch],
        release_matches: Sequence[SpotifyVinylReleaseMatch],
    ) -> None:
        db.add_all(
            [
                *artist_stats,
                *album_stats,
                *track_stats,
                *hourly_stats,
                *monthly_artist_stats,
                *skip_stats,
                *artist_matches,
                *release_matches,
            ]
        )
        db.flush()

    @staticmethod
    def list_top_artists(db: Session, *, limit: int = 20) -> list[SpotifyArtistStats]:
        return (
            db.query(SpotifyArtistStats)
            .order_by(SpotifyArtistStats.total_ms_played.desc(), SpotifyArtistStats.play_count.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def list_top_albums(db: Session, *, limit: int = 20) -> list[SpotifyAlbumStats]:
        return (
            db.query(SpotifyAlbumStats)
            .order_by(SpotifyAlbumStats.total_ms_played.desc(), SpotifyAlbumStats.play_count.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def list_top_tracks(db: Session, *, limit: int = 20) -> list[SpotifyTrackStats]:
        return (
            db.query(SpotifyTrackStats)
            .order_by(SpotifyTrackStats.total_ms_played.desc(), SpotifyTrackStats.play_count.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def list_hourly_stats(db: Session) -> list[SpotifyHourlyStats]:
        return db.query(SpotifyHourlyStats).order_by(SpotifyHourlyStats.played_hour.asc()).all()

    @staticmethod
    def list_monthly_artist_stats(
        db: Session,
        *,
        normalized_artist_name: str | None = None,
    ) -> list[SpotifyMonthlyArtistStats]:
        query = db.query(SpotifyMonthlyArtistStats)
        if normalized_artist_name is not None:
            query = query.filter(SpotifyMonthlyArtistStats.normalized_artist_name == normalized_artist_name)
        return query.order_by(SpotifyMonthlyArtistStats.played_year_month.asc()).all()

    @staticmethod
    def list_skip_stats(db: Session) -> list[SpotifySkipStats]:
        return db.query(SpotifySkipStats).order_by(SpotifySkipStats.play_count.desc()).all()

    @staticmethod
    def list_artist_matches(db: Session, *, limit: int = 20) -> list[SpotifyVinylArtistMatch]:
        return (
            db.query(SpotifyVinylArtistMatch)
            .order_by(SpotifyVinylArtistMatch.confidence_score.desc(), SpotifyVinylArtistMatch.release_count.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def list_release_matches(db: Session, *, limit: int = 20) -> list[SpotifyVinylReleaseMatch]:
        return (
            db.query(SpotifyVinylReleaseMatch)
            .order_by(
                SpotifyVinylReleaseMatch.confidence_score.desc(),
                SpotifyVinylReleaseMatch.spotify_album_name.asc(),
            )
            .limit(limit)
            .all()
        )

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
