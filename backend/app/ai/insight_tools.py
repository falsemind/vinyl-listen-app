from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.chat_adapter import AiChatToolResult
from app.repositories.sessions_repository import SessionsRepository
from app.repositories.spotify_listening_repository import SpotifyListeningRepository
from app.services.analytics_service import AnalyticsService


class AiInsightToolRunner:
    """Runs deterministic read-only collection tools for the AI Insights adapter."""

    def __init__(
        self,
        analytics_service: AnalyticsService | None = None,
        sessions_repository: SessionsRepository | None = None,
        spotify_repository: SpotifyListeningRepository | None = None,
    ) -> None:
        self.analytics_service = analytics_service or AnalyticsService()
        self.sessions_repository = sessions_repository or SessionsRepository()
        self.spotify_repository = spotify_repository or SpotifyListeningRepository()

    def run(self, db: Session, *, user_id: str, message: str) -> list[AiChatToolResult]:
        normalized_message = message.lower()
        spotify_requested = self._should_include_spotify_tools(normalized_message)
        results = [self._listening_summary(db, user_id=user_id)]

        if self._should_include_session_notes(normalized_message):
            results.append(self._session_notes(db, user_id=user_id))
        if self._mentions_any(normalized_message, ("recent", "lately", "latest", "night", "month", "recommend")):
            results.append(self._recent_sessions(db, user_id=user_id))
        if self._mentions_any(normalized_message, ("top", "most", "record", "recommend", "played", "play")):
            results.append(self._top_records(db, user_id=user_id))
        if self._mentions_any(normalized_message, ("style", "genre")):
            results.append(self._style_distribution(db, user_id=user_id))
        if "mood" in normalized_message:
            results.append(self._mood_distribution(db, user_id=user_id))
        if "rating" in normalized_message or "rated" in normalized_message:
            results.append(self._rating_distribution(db, user_id=user_id))
        if spotify_requested:
            results.append(self._spotify_vinyl_overlap_summary(db, user_id=user_id))
            results.append(self._spotify_top_artists_by_period(db, user_id=user_id))
            if self._mentions_any(
                normalized_message,
                ("time", "hour", "night", "morning", "day", "pattern", "when"),
            ):
                results.append(self._spotify_listening_time_patterns(db, user_id=user_id))
            if self._mentions_any(
                normalized_message,
                ("recommend", "recommendation", "suggest", "collection", "record", "vinyl"),
            ):
                results.append(self._spotify_collection_recommendation_signals(db, user_id=user_id))

        return [result for result in results if result.content.strip()]

    def _listening_summary(self, db: Session, *, user_id: str) -> AiChatToolResult:
        total_sessions = self.sessions_repository.count_all(db, user_id=user_id)
        return AiChatToolResult(
            name="get_listening_summary",
            content=f"Total logged listening sessions: {total_sessions}.",
        )

    def _recent_sessions(self, db: Session, *, user_id: str) -> AiChatToolResult:
        rows = self.sessions_repository.get_recent_with_releases(db, user_id=user_id, limit=5)
        rows += self.sessions_repository.get_recent_with_manual_releases(db, user_id=user_id, limit=5)
        rows = self._sort_recent_session_rows(rows)[:5]
        if not rows:
            return AiChatToolResult(name="get_recent_sessions", content="No listening sessions are logged yet.")

        lines = []
        for session, release in rows:
            played_at = self._format_datetime(session.played_at or session.created_at)
            details = [f"{played_at}: {release.artist} - {release.title}"]
            if session.mood:
                details.append(f"mood={session.mood}")
            if session.rating is not None:
                details.append(f"rating={session.rating}")
            if session.vinyl_side:
                details.append(f"side={session.vinyl_side}")
            lines.append("; ".join(details))
        return AiChatToolResult(name="get_recent_sessions", content="\n".join(lines))

    def _session_notes(self, db: Session, *, user_id: str) -> AiChatToolResult:
        rows = self.sessions_repository.get_recent_notes_with_releases(db, user_id=user_id, limit=8)
        rows += self.sessions_repository.get_recent_notes_with_manual_releases(db, user_id=user_id, limit=8)
        rows = self._sort_recent_session_rows(rows)[:8]
        if not rows:
            return AiChatToolResult(name="get_session_notes", content="No saved session notes are available yet.")

        lines = []
        for session, release in rows:
            note = self._clean_note_text(session.notes)
            if not note:
                continue
            played_at = self._format_datetime(session.played_at or session.created_at)
            details = [f"{played_at}: {release.artist} - {release.title}"]
            if session.mood:
                details.append(f"mood={session.mood}")
            if session.rating is not None:
                details.append(f"rating={session.rating}")
            if session.vinyl_side:
                details.append(f"side={session.vinyl_side}")
            details.append(f'note="{note}"')
            lines.append("; ".join(details))
        return AiChatToolResult(name="get_session_notes", content="\n".join(lines))

    def _top_records(self, db: Session, *, user_id: str) -> AiChatToolResult:
        records = self.analytics_service.get_top_records(db, user_id=user_id, limit=5)
        if not records:
            return AiChatToolResult(name="get_top_records", content="No top records are available yet.")

        lines = []
        for record in records:
            average_rating = f"{record.average_rating:.1f}" if record.average_rating is not None else "unrated"
            styles = ", ".join(record.release.styles or []) or "unknown styles"
            lines.append(
                f"{record.release.artist} - {record.release.title}: plays={record.plays}, "
                f"average_rating={average_rating}, styles={styles}"
            )
        return AiChatToolResult(name="get_top_records", content="\n".join(lines))

    @staticmethod
    def _sort_recent_session_rows(rows):
        return sorted(
            rows,
            key=lambda row: (row[0].played_at or row[0].created_at, row[0].created_at),
            reverse=True,
        )

    def _style_distribution(self, db: Session, *, user_id: str) -> AiChatToolResult:
        distribution = self.analytics_service.get_style_distribution(db, user_id=user_id)
        return AiChatToolResult(
            name="get_style_distribution",
            content=self._render_distribution(distribution, empty_message="No style data is available yet."),
        )

    def _mood_distribution(self, db: Session, *, user_id: str) -> AiChatToolResult:
        distribution = self.analytics_service.get_mood_distribution(db, user_id=user_id)
        return AiChatToolResult(
            name="get_mood_distribution",
            content=self._render_distribution(distribution, empty_message="No mood data is available yet."),
        )

    def _rating_distribution(self, db: Session, *, user_id: str) -> AiChatToolResult:
        distribution = self.analytics_service.get_rating_distribution(db, user_id=user_id)
        return AiChatToolResult(
            name="get_rating_distribution",
            content=self._render_distribution(distribution, empty_message="No rating data is available yet."),
        )

    def _spotify_vinyl_overlap_summary(self, db: Session, *, user_id: str) -> AiChatToolResult:
        artist_matches = self.spotify_repository.list_artist_matches(db, user_id=user_id, limit=5)
        release_matches = self.spotify_repository.list_release_matches(db, user_id=user_id, limit=5)
        if not artist_matches and not release_matches:
            return AiChatToolResult(
                name="get_spotify_vinyl_overlap_summary",
                content=(
                    "No Spotify-to-vinyl overlap is available yet. " "Import Spotify history and refresh rollups first."
                ),
            )

        lines = []
        for match in artist_matches:
            release_ids = ", ".join(str(release_id) for release_id in match.release_ids[:3])
            lines.append(
                f"Artist overlap: {match.artist_name}; known_releases={match.release_count}; "
                f"release_ids={release_ids}; confidence={match.confidence_score}; "
                f"match_type={match.match_type}; reason={match.explanation}"
            )
        for match in release_matches:
            lines.append(
                f"Release overlap: {match.spotify_artist_name} - {match.spotify_album_name}; "
                f"known_release={match.release_artist} - {match.release_title}; "
                f"release_id={match.release_id}; confidence={match.confidence_score}; "
                f"match_type={match.match_type}; reason={match.explanation}"
            )
        return AiChatToolResult(name="get_spotify_vinyl_overlap_summary", content="\n".join(lines))

    def _spotify_listening_time_patterns(self, db: Session, *, user_id: str) -> AiChatToolResult:
        hourly_stats = self.spotify_repository.list_hourly_stats(db, user_id=user_id)
        if not hourly_stats:
            return AiChatToolResult(
                name="get_spotify_listening_time_patterns",
                content="No Spotify listening time pattern data is available yet.",
            )

        top_hours = sorted(hourly_stats, key=lambda stat: stat.total_ms_played, reverse=True)[:5]
        lines = [
            (
                f"{stat.played_hour:02d}:00: plays={stat.play_count}; meaningful={stat.meaningful_play_count}; "
                f"skipped={stat.skipped_count}; total_minutes={self._format_minutes(stat.total_ms_played)}"
            )
            for stat in top_hours
        ]
        return AiChatToolResult(name="get_spotify_listening_time_patterns", content="\n".join(lines))

    def _spotify_top_artists_by_period(self, db: Session, *, user_id: str) -> AiChatToolResult:
        top_artists = self.spotify_repository.list_top_artists(db, user_id=user_id, limit=5)
        if not top_artists:
            return AiChatToolResult(
                name="get_spotify_top_artists_by_period",
                content="No Spotify artist rollups are available yet.",
            )

        lines = []
        for artist in top_artists:
            lines.append(
                f"Top Spotify artist: {artist.artist_name}; plays={artist.play_count}; "
                f"meaningful={artist.meaningful_play_count}; skipped={artist.skipped_count}; "
                f"total_minutes={self._format_minutes(artist.total_ms_played)}; "
                f"first_played={self._format_datetime(artist.first_played_at)}; "
                f"last_played={self._format_datetime(artist.last_played_at)}"
            )

        top_artist = top_artists[0]
        monthly_stats = self.spotify_repository.list_monthly_artist_stats(
            db,
            user_id=user_id,
            normalized_artist_name=top_artist.normalized_artist_name,
        )
        for stat in monthly_stats[-5:]:
            lines.append(
                f"Monthly Spotify signal: {stat.played_year_month}; artist={stat.artist_name}; "
                f"plays={stat.play_count}; meaningful={stat.meaningful_play_count}; "
                f"total_minutes={self._format_minutes(stat.total_ms_played)}"
            )
        return AiChatToolResult(name="get_spotify_top_artists_by_period", content="\n".join(lines))

    def _spotify_collection_recommendation_signals(self, db: Session, *, user_id: str) -> AiChatToolResult:
        release_matches = self.spotify_repository.list_release_matches(db, user_id=user_id, limit=5)
        if not release_matches:
            return AiChatToolResult(
                name="get_spotify_collection_recommendation_signals",
                content=(
                    "No Spotify collection recommendation signals are available yet. "
                    "Recommendations remain limited to known releases."
                ),
            )

        lines = []
        for match in release_matches:
            lines.append(
                f"Collection recommendation signal: {match.release_artist} - {match.release_title}; "
                f"release_id={match.release_id}; spotify_match={match.spotify_artist_name} - "
                f"{match.spotify_album_name}; confidence={match.confidence_score}; "
                f"match_type={match.match_type}; reason={match.explanation}"
            )
        return AiChatToolResult(name="get_spotify_collection_recommendation_signals", content="\n".join(lines))

    def _render_distribution(self, distribution: dict[str, int], *, empty_message: str) -> str:
        positive_items = [(name, count) for name, count in distribution.items() if count > 0]
        if not positive_items:
            return empty_message
        return "\n".join(f"{name}: {count}" for name, count in positive_items[:10])

    def _mentions_any(self, message: str, terms: tuple[str, ...]) -> bool:
        return any(term in message for term in terms)

    def _should_include_session_notes(self, message: str) -> bool:
        return self._mentions_any(
            message,
            (
                "note",
                "thought",
                "impression",
                "feeling",
                "felt",
                "special",
                "recommend",
                "suggest",
                "why",
            ),
        )

    def _should_include_spotify_tools(self, message: str) -> bool:
        return self._mentions_any(
            message,
            (
                "spotify",
                "streaming",
                "streamed",
                "listen history",
                "listening history",
                "overlap",
                "correlation",
            ),
        )

    def _clean_note_text(self, value: str | None) -> str:
        cleaned_value = " ".join((value or "").split())
        if len(cleaned_value) <= 280:
            return cleaned_value
        return f"{cleaned_value[:277]}..."

    def _format_minutes(self, value: int | None) -> str:
        if value is None:
            return "0.0"
        return f"{value / 60000:.1f}"

    def _format_datetime(self, value: datetime | None) -> str:
        if value is None:
            return "unknown date"
        return value.date().isoformat()
