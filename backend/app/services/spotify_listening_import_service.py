import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.spotify_listening import SpotifyListeningEvent
from app.repositories.spotify_listening_repository import SpotifyListeningRepository
from app.services.spotify_listening_rollup_service import SpotifyListeningRollupService
from app.utils.spotify_text import normalize_spotify_text, stable_spotify_key

logger = logging.getLogger(__name__)

DEFAULT_MEANINGFUL_LISTEN_THRESHOLD_MS = 30_000
MAX_ERROR_SUMMARY_ITEMS = 20


@dataclass(frozen=True)
class SpotifyListeningImportResult:
    batch_id: str
    source_paths: list[str]
    total_items: int
    imported_count: int
    duplicate_count: int
    skipped_count: int
    error_count: int
    error_summary: list[str]


@dataclass
class _ImportCounts:
    total_items: int = 0
    imported_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0
    error_count: int = 0


class SpotifyListeningImportItemError(ValueError):
    """Raised when one Spotify history item cannot be converted into a song event."""


class SpotifyListeningImportService:
    def __init__(
        self,
        repository: SpotifyListeningRepository | None = None,
        rollup_service: SpotifyListeningRollupService | None = None,
        *,
        meaningful_listen_threshold_ms: int = DEFAULT_MEANINGFUL_LISTEN_THRESHOLD_MS,
    ) -> None:
        self._repository = repository or SpotifyListeningRepository()
        self._rollup_service = rollup_service or SpotifyListeningRollupService(repository=self._repository)
        self._meaningful_listen_threshold_ms = meaningful_listen_threshold_ms

    def import_files(
        self,
        db: Session,
        file_paths: Sequence[str | Path],
        *,
        user_id: str,
        batch_size: int = 1_000,
        refresh_rollups: bool = True,
    ) -> SpotifyListeningImportResult:
        if not file_paths:
            raise ValueError("At least one Spotify listening-history file path is required")
        if batch_size < 1:
            raise ValueError("batch_size must be greater than zero")

        source_paths = [str(Path(file_path)) for file_path in file_paths]
        batch = self._repository.create_import_batch(db, user_id=user_id, source_paths=source_paths)
        counts = _ImportCounts()
        error_summary: list[str] = []
        pending_events: list[SpotifyListeningEvent] = []
        seen_event_keys: set[str] = set()

        logger.info("Importing Spotify listening history batch_id=%s files=%s", batch.id, len(source_paths))

        try:
            for file_path in file_paths:
                for item in self._load_items(Path(file_path)):
                    counts.total_items += 1
                    try:
                        event = self._map_item(item, user_id=user_id, import_batch_id=batch.id)
                    except SpotifyListeningImportItemError as error:
                        counts.skipped_count += 1
                        counts.error_count += 1
                        self._append_error(error_summary, f"item {counts.total_items}: {error}")
                        continue

                    if event is None:
                        counts.skipped_count += 1
                        continue

                    if event.event_key in seen_event_keys:
                        counts.duplicate_count += 1
                        continue

                    seen_event_keys.add(event.event_key)
                    pending_events.append(event)

                    if len(pending_events) >= batch_size:
                        self._flush_events(db, user_id=user_id, events=pending_events, counts=counts)
                        pending_events.clear()

            if pending_events:
                self._flush_events(db, user_id=user_id, events=pending_events, counts=counts)

            if refresh_rollups:
                self._rollup_service.refresh(db, user_id=user_id, commit=False)

            completed_batch = self._repository.mark_completed(
                db,
                batch.id,
                user_id=user_id,
                total_items=counts.total_items,
                imported_count=counts.imported_count,
                duplicate_count=counts.duplicate_count,
                skipped_count=counts.skipped_count,
                error_count=counts.error_count,
                error_summary=error_summary,
            )
        except Exception as error:
            db.rollback()
            self._append_error(error_summary, str(error))
            self._repository.mark_failed(
                db,
                batch.id,
                user_id=user_id,
                total_items=counts.total_items,
                imported_count=counts.imported_count,
                duplicate_count=counts.duplicate_count,
                skipped_count=counts.skipped_count,
                error_count=counts.error_count + 1,
                error_summary=error_summary,
            )
            raise

        logger.info(
            "Imported Spotify listening history batch_id=%s imported=%s duplicates=%s skipped=%s errors=%s",
            completed_batch.id,
            completed_batch.imported_count,
            completed_batch.duplicate_count,
            completed_batch.skipped_count,
            completed_batch.error_count,
        )
        return SpotifyListeningImportResult(
            batch_id=completed_batch.id,
            source_paths=list(completed_batch.source_paths),
            total_items=completed_batch.total_items,
            imported_count=completed_batch.imported_count,
            duplicate_count=completed_batch.duplicate_count,
            skipped_count=completed_batch.skipped_count,
            error_count=completed_batch.error_count,
            error_summary=list(completed_batch.error_summary or []),
        )

    def _flush_events(
        self,
        db: Session,
        *,
        user_id: str,
        events: Sequence[SpotifyListeningEvent],
        counts: _ImportCounts,
    ) -> None:
        imported_count, duplicate_count = self._repository.add_new_events(db, user_id=user_id, events=events)
        counts.imported_count += imported_count
        counts.duplicate_count += duplicate_count

    def _load_items(self, file_path: Path) -> Iterable[Any]:
        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        if not isinstance(payload, list):
            raise ValueError(f"Spotify listening-history file must contain a JSON array: {file_path}")

        yield from payload

    def _map_item(self, item: dict[str, Any], *, user_id: str, import_batch_id: str) -> SpotifyListeningEvent | None:
        if not isinstance(item, dict):
            raise SpotifyListeningImportItemError("item is not a JSON object")

        track_name = _clean_text(item.get("master_metadata_track_name"), max_length=512)
        artist_name = _clean_text(item.get("master_metadata_album_artist_name"), max_length=512)
        album_name = _clean_text(item.get("master_metadata_album_album_name"), max_length=512)

        if track_name is None or artist_name is None:
            return None

        played_at = _parse_played_at(item.get("ts"))
        ms_played = _parse_ms_played(item.get("ms_played"))
        normalized_track_name = normalize_spotify_text(track_name)
        normalized_artist_name = normalize_spotify_text(artist_name)
        normalized_album_name = normalize_spotify_text(album_name) if album_name is not None else None
        event_key = _event_key(
            played_at=played_at,
            ms_played=ms_played,
            normalized_artist_name=normalized_artist_name,
            normalized_album_name=normalized_album_name,
            normalized_track_name=normalized_track_name,
            reason_start=_clean_text(item.get("reason_start"), max_length=64),
            reason_end=_clean_text(item.get("reason_end"), max_length=64),
        )

        return SpotifyListeningEvent(
            user_id=user_id,
            import_batch_id=import_batch_id,
            event_key=event_key,
            played_at=played_at,
            played_date=played_at.date(),
            played_hour=played_at.hour,
            played_weekday=played_at.weekday(),
            played_year_month=f"{played_at.year:04d}-{played_at.month:02d}",
            ms_played=ms_played,
            conn_country=_clean_text(item.get("conn_country"), max_length=16),
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            normalized_track_name=normalized_track_name,
            normalized_artist_name=normalized_artist_name,
            normalized_album_name=normalized_album_name,
            reason_start=_clean_text(item.get("reason_start"), max_length=64),
            reason_end=_clean_text(item.get("reason_end"), max_length=64),
            shuffle=_parse_optional_bool(item.get("shuffle")),
            skipped=_parse_optional_bool(item.get("skipped")),
            offline=_parse_optional_bool(item.get("offline")),
            offline_timestamp=_clean_text(item.get("offline_timestamp"), max_length=64),
            is_meaningful_listen=ms_played >= self._meaningful_listen_threshold_ms,
        )

    @staticmethod
    def _append_error(error_summary: list[str], message: str) -> None:
        if len(error_summary) < MAX_ERROR_SUMMARY_ITEMS:
            error_summary.append(message)


def _parse_played_at(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise SpotifyListeningImportItemError("ts is required")

    raw_value = value.strip()
    try:
        if raw_value.endswith("Z"):
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        elif "T" in raw_value:
            parsed = datetime.fromisoformat(raw_value)
        else:
            parsed = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError as error:
        raise SpotifyListeningImportItemError(f"ts is invalid: {raw_value}") from error

    return parsed.astimezone(UTC) if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _parse_ms_played(value: Any) -> int:
    if value is None:
        return 0

    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise SpotifyListeningImportItemError(f"ms_played is invalid: {value}") from error

    return max(parsed, 0)


def _parse_optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _clean_text(value: Any, *, max_length: int) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()
    if not cleaned:
        return None

    return cleaned[:max_length]


def _event_key(
    *,
    played_at: datetime,
    ms_played: int,
    normalized_artist_name: str,
    normalized_album_name: str | None,
    normalized_track_name: str,
    reason_start: str | None,
    reason_end: str | None,
) -> str:
    parts = [
        played_at.isoformat(),
        str(ms_played),
        normalized_artist_name,
        normalized_album_name or "",
        normalized_track_name,
        reason_start or "",
        reason_end or "",
    ]
    return stable_spotify_key(parts)
