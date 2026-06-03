from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.models.spotify_listening import (
    SpotifyAlbumStats,
    SpotifyArtistStats,
    SpotifyHourlyStats,
    SpotifyListeningEvent,
    SpotifyMonthlyArtistStats,
    SpotifySkipStats,
    SpotifyTrackStats,
    SpotifyVinylArtistMatch,
    SpotifyVinylReleaseMatch,
)
from app.repositories.spotify_listening_repository import SpotifyListeningRepository
from app.utils.spotify_text import normalize_spotify_text, stable_spotify_key


@dataclass(frozen=True)
class SpotifyListeningRollupRefreshResult:
    artist_stats_count: int
    album_stats_count: int
    track_stats_count: int
    hourly_stats_count: int
    monthly_artist_stats_count: int
    skip_stats_count: int
    artist_match_count: int
    release_match_count: int


@dataclass
class _ListeningStatsAccumulator:
    artist_name: str | None = None
    album_name: str | None = None
    track_name: str | None = None
    play_count: int = 0
    meaningful_play_count: int = 0
    skipped_count: int = 0
    total_ms_played: int = 0
    first_played_at: datetime | None = None
    last_played_at: datetime | None = None

    def add(self, event: SpotifyListeningEvent) -> None:
        self.artist_name = self.artist_name or event.artist_name
        self.album_name = self.album_name or event.album_name
        self.track_name = self.track_name or event.track_name
        self.play_count += 1
        self.meaningful_play_count += 1 if event.is_meaningful_listen else 0
        self.skipped_count += 1 if event.skipped is True else 0
        self.total_ms_played += event.ms_played
        self.first_played_at = (
            event.played_at if self.first_played_at is None else min(self.first_played_at, event.played_at)
        )
        self.last_played_at = (
            event.played_at if self.last_played_at is None else max(self.last_played_at, event.played_at)
        )


@dataclass
class _CounterAccumulator:
    play_count: int = 0
    meaningful_play_count: int = 0
    skipped_count: int = 0
    total_ms_played: int = 0

    def add(self, event: SpotifyListeningEvent) -> None:
        self.play_count += 1
        self.meaningful_play_count += 1 if event.is_meaningful_listen else 0
        self.skipped_count += 1 if event.skipped is True else 0
        self.total_ms_played += event.ms_played


@dataclass(frozen=True)
class _ReleaseCandidate:
    release_id: str
    artist: str
    title: str


class SpotifyListeningRollupService:
    def __init__(self, repository: SpotifyListeningRepository | None = None) -> None:
        self._repository = repository or SpotifyListeningRepository()

    def refresh(self, db: Session, *, commit: bool = True) -> SpotifyListeningRollupRefreshResult:
        artist_stats: dict[str, _ListeningStatsAccumulator] = defaultdict(_ListeningStatsAccumulator)
        album_stats: dict[tuple[str, str], _ListeningStatsAccumulator] = defaultdict(_ListeningStatsAccumulator)
        track_stats: dict[tuple[str, str | None, str], _ListeningStatsAccumulator] = defaultdict(
            _ListeningStatsAccumulator
        )
        hourly_stats: dict[int, _CounterAccumulator] = defaultdict(_CounterAccumulator)
        monthly_artist_stats: dict[tuple[str, str], _ListeningStatsAccumulator] = defaultdict(
            _ListeningStatsAccumulator
        )
        skip_stats: dict[tuple[bool | None, str | None], _CounterAccumulator] = defaultdict(_CounterAccumulator)

        for event in db.query(SpotifyListeningEvent).yield_per(1_000):
            artist_stats[event.normalized_artist_name].add(event)

            if event.normalized_album_name is not None:
                album_stats[(event.normalized_artist_name, event.normalized_album_name)].add(event)

            track_stats[(event.normalized_artist_name, event.normalized_album_name, event.normalized_track_name)].add(
                event
            )
            hourly_stats[event.played_hour].add(event)
            monthly_artist_stats[(event.played_year_month, event.normalized_artist_name)].add(event)
            skip_stats[(event.skipped, event.reason_end)].add(event)

        artist_rows = [
            SpotifyArtistStats(
                normalized_artist_name=normalized_artist_name,
                artist_name=stats.artist_name or normalized_artist_name,
                play_count=stats.play_count,
                meaningful_play_count=stats.meaningful_play_count,
                skipped_count=stats.skipped_count,
                total_ms_played=stats.total_ms_played,
                first_played_at=_required_datetime(stats.first_played_at),
                last_played_at=_required_datetime(stats.last_played_at),
            )
            for normalized_artist_name, stats in artist_stats.items()
        ]
        album_rows = [
            SpotifyAlbumStats(
                stat_key=stable_spotify_key([normalized_artist_name, normalized_album_name]),
                normalized_artist_name=normalized_artist_name,
                normalized_album_name=normalized_album_name,
                artist_name=stats.artist_name or normalized_artist_name,
                album_name=stats.album_name or normalized_album_name,
                play_count=stats.play_count,
                meaningful_play_count=stats.meaningful_play_count,
                skipped_count=stats.skipped_count,
                total_ms_played=stats.total_ms_played,
                first_played_at=_required_datetime(stats.first_played_at),
                last_played_at=_required_datetime(stats.last_played_at),
            )
            for (normalized_artist_name, normalized_album_name), stats in album_stats.items()
        ]
        track_rows = [
            SpotifyTrackStats(
                stat_key=stable_spotify_key([normalized_artist_name, normalized_album_name, normalized_track_name]),
                normalized_artist_name=normalized_artist_name,
                normalized_album_name=normalized_album_name,
                normalized_track_name=normalized_track_name,
                artist_name=stats.artist_name or normalized_artist_name,
                album_name=stats.album_name,
                track_name=stats.track_name or normalized_track_name,
                play_count=stats.play_count,
                meaningful_play_count=stats.meaningful_play_count,
                skipped_count=stats.skipped_count,
                total_ms_played=stats.total_ms_played,
                first_played_at=_required_datetime(stats.first_played_at),
                last_played_at=_required_datetime(stats.last_played_at),
            )
            for (normalized_artist_name, normalized_album_name, normalized_track_name), stats in track_stats.items()
        ]
        hourly_rows = [
            SpotifyHourlyStats(
                played_hour=played_hour,
                play_count=stats.play_count,
                meaningful_play_count=stats.meaningful_play_count,
                skipped_count=stats.skipped_count,
                total_ms_played=stats.total_ms_played,
            )
            for played_hour, stats in hourly_stats.items()
        ]
        monthly_artist_rows = [
            SpotifyMonthlyArtistStats(
                stat_key=stable_spotify_key([played_year_month, normalized_artist_name]),
                played_year_month=played_year_month,
                normalized_artist_name=normalized_artist_name,
                artist_name=stats.artist_name or normalized_artist_name,
                play_count=stats.play_count,
                meaningful_play_count=stats.meaningful_play_count,
                skipped_count=stats.skipped_count,
                total_ms_played=stats.total_ms_played,
            )
            for (played_year_month, normalized_artist_name), stats in monthly_artist_stats.items()
        ]
        skip_rows = [
            SpotifySkipStats(
                stat_key=stable_spotify_key([str(skipped), reason_end]),
                skipped=skipped,
                reason_end=reason_end,
                play_count=stats.play_count,
                skipped_count=stats.skipped_count,
                total_ms_played=stats.total_ms_played,
            )
            for (skipped, reason_end), stats in skip_stats.items()
        ]

        artist_matches, release_matches = self._build_collection_matches(db, artist_rows, album_rows)

        self._repository.clear_rollups_and_matches(db)
        self._repository.add_rollups_and_matches(
            db,
            artist_stats=artist_rows,
            album_stats=album_rows,
            track_stats=track_rows,
            hourly_stats=hourly_rows,
            monthly_artist_stats=monthly_artist_rows,
            skip_stats=skip_rows,
            artist_matches=artist_matches,
            release_matches=release_matches,
        )

        if commit:
            db.commit()

        return SpotifyListeningRollupRefreshResult(
            artist_stats_count=len(artist_rows),
            album_stats_count=len(album_rows),
            track_stats_count=len(track_rows),
            hourly_stats_count=len(hourly_rows),
            monthly_artist_stats_count=len(monthly_artist_rows),
            skip_stats_count=len(skip_rows),
            artist_match_count=len(artist_matches),
            release_match_count=len(release_matches),
        )

    def _build_collection_matches(
        self,
        db: Session,
        artist_stats: list[SpotifyArtistStats],
        album_stats: list[SpotifyAlbumStats],
    ) -> tuple[list[SpotifyVinylArtistMatch], list[SpotifyVinylReleaseMatch]]:
        releases_by_artist: dict[str, list[_ReleaseCandidate]] = defaultdict(list)
        releases_by_artist_title: dict[tuple[str, str], list[_ReleaseCandidate]] = defaultdict(list)

        for release_id, artist, title in db.query(Releases.id, Releases.artist, Releases.title).all():
            normalized_artist = normalize_spotify_text(artist)
            normalized_title = normalize_spotify_text(title)
            candidate = _ReleaseCandidate(release_id=release_id, artist=artist, title=title)
            releases_by_artist[normalized_artist].append(candidate)
            releases_by_artist_title[(normalized_artist, normalized_title)].append(candidate)

        artist_matches: list[SpotifyVinylArtistMatch] = []
        for artist_stat in artist_stats:
            candidates = releases_by_artist.get(artist_stat.normalized_artist_name, [])
            if not candidates:
                continue

            release_ids = sorted(candidate.release_id for candidate in candidates)
            artist_matches.append(
                SpotifyVinylArtistMatch(
                    normalized_artist_name=artist_stat.normalized_artist_name,
                    artist_name=artist_stat.artist_name,
                    release_ids=release_ids,
                    release_count=len(release_ids),
                    confidence_score=100,
                    match_type="artist_exact",
                    explanation=(
                        f'Exact normalized artist match for "{artist_stat.artist_name}" '
                        f"against {len(release_ids)} known release(s)."
                    ),
                )
            )

        release_matches: list[SpotifyVinylReleaseMatch] = []
        for album_stat in album_stats:
            candidates = releases_by_artist_title.get(
                (album_stat.normalized_artist_name, album_stat.normalized_album_name),
                [],
            )
            for candidate in candidates:
                release_matches.append(
                    SpotifyVinylReleaseMatch(
                        match_key=stable_spotify_key(
                            [candidate.release_id, album_stat.normalized_artist_name, album_stat.normalized_album_name]
                        ),
                        release_id=candidate.release_id,
                        normalized_artist_name=album_stat.normalized_artist_name,
                        normalized_album_name=album_stat.normalized_album_name,
                        spotify_artist_name=album_stat.artist_name,
                        spotify_album_name=album_stat.album_name,
                        release_artist=candidate.artist,
                        release_title=candidate.title,
                        confidence_score=100,
                        match_type="artist_album_exact",
                        explanation=(
                            f'Exact normalized artist and album match for "{album_stat.artist_name} - '
                            f'{album_stat.album_name}" against known release "{candidate.artist} - {candidate.title}".'
                        ),
                    )
                )

        return artist_matches, release_matches


def _required_datetime(value: datetime | None) -> datetime:
    if value is None:
        raise ValueError("Spotify rollup stats require at least one event")
    return value
