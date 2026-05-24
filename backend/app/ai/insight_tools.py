from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.chat_adapter import AiChatToolResult
from app.repositories.sessions_repository import SessionsRepository
from app.services.analytics_service import AnalyticsService


class AiInsightToolRunner:
    """Runs deterministic read-only collection tools for the AI Insights adapter."""

    def __init__(
        self,
        analytics_service: AnalyticsService | None = None,
        sessions_repository: SessionsRepository | None = None,
    ) -> None:
        self.analytics_service = analytics_service or AnalyticsService()
        self.sessions_repository = sessions_repository or SessionsRepository()

    def run(self, db: Session, *, message: str) -> list[AiChatToolResult]:
        normalized_message = message.lower()
        results = [self._listening_summary(db)]

        if self._should_include_session_notes(normalized_message):
            results.append(self._session_notes(db))
        if self._mentions_any(normalized_message, ("recent", "lately", "latest", "night", "month", "recommend")):
            results.append(self._recent_sessions(db))
        if self._mentions_any(normalized_message, ("top", "most", "record", "recommend", "played", "play")):
            results.append(self._top_records(db))
        if self._mentions_any(normalized_message, ("style", "genre")):
            results.append(self._style_distribution(db))
        if "mood" in normalized_message:
            results.append(self._mood_distribution(db))
        if "rating" in normalized_message or "rated" in normalized_message:
            results.append(self._rating_distribution(db))

        return [result for result in results if result.content.strip()]

    def _listening_summary(self, db: Session) -> AiChatToolResult:
        total_sessions = self.sessions_repository.count_all(db)
        return AiChatToolResult(
            name="get_listening_summary",
            content=f"Total logged listening sessions: {total_sessions}.",
        )

    def _recent_sessions(self, db: Session) -> AiChatToolResult:
        rows = self.sessions_repository.get_recent_with_releases(db, limit=5)
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

    def _session_notes(self, db: Session) -> AiChatToolResult:
        rows = self.sessions_repository.get_recent_notes_with_releases(db, limit=8)
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

    def _top_records(self, db: Session) -> AiChatToolResult:
        records = self.analytics_service.get_top_records(db, limit=5)
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

    def _style_distribution(self, db: Session) -> AiChatToolResult:
        distribution = self.analytics_service.get_style_distribution(db)
        return AiChatToolResult(
            name="get_style_distribution",
            content=self._render_distribution(distribution, empty_message="No style data is available yet."),
        )

    def _mood_distribution(self, db: Session) -> AiChatToolResult:
        distribution = self.analytics_service.get_mood_distribution(db)
        return AiChatToolResult(
            name="get_mood_distribution",
            content=self._render_distribution(distribution, empty_message="No mood data is available yet."),
        )

    def _rating_distribution(self, db: Session) -> AiChatToolResult:
        distribution = self.analytics_service.get_rating_distribution(db)
        return AiChatToolResult(
            name="get_rating_distribution",
            content=self._render_distribution(distribution, empty_message="No rating data is available yet."),
        )

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

    def _clean_note_text(self, value: str | None) -> str:
        cleaned_value = " ".join((value or "").split())
        if len(cleaned_value) <= 280:
            return cleaned_value
        return f"{cleaned_value[:277]}..."

    def _format_datetime(self, value: datetime | None) -> str:
        if value is None:
            return "unknown date"
        return value.date().isoformat()
