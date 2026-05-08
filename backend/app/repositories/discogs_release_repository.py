from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.discogs_release_cache import DiscogsReleaseCache


class DiscogsReleaseRepository:
    @staticmethod
    def get_by_discogs_release_id(db: Session, discogs_release_id: int) -> DiscogsReleaseCache | None:
        return (
            db.query(DiscogsReleaseCache)
            .filter(DiscogsReleaseCache.discogs_release_id == discogs_release_id)
            .one_or_none()
        )

    @staticmethod
    def touch(db: Session, cache_entry: DiscogsReleaseCache) -> DiscogsReleaseCache:
        cache_entry.last_accessed_at = datetime.now(UTC)
        db.add(cache_entry)
        db.commit()
        db.refresh(cache_entry)
        return cache_entry

    @staticmethod
    def upsert(db: Session, discogs_release_id: int, raw_discogs_json: dict) -> DiscogsReleaseCache:
        cache_entry = DiscogsReleaseRepository.get_by_discogs_release_id(db, discogs_release_id)
        now = datetime.now(UTC)

        if cache_entry is None:
            cache_entry = DiscogsReleaseCache(
                discogs_release_id=discogs_release_id,
                raw_discogs_json=raw_discogs_json,
                cached_at=now,
                last_accessed_at=now,
            )
        else:
            cache_entry.raw_discogs_json = raw_discogs_json
            cache_entry.cached_at = now
            cache_entry.last_accessed_at = now

        db.add(cache_entry)
        db.commit()
        db.refresh(cache_entry)
        return cache_entry
