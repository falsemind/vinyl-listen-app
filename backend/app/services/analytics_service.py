import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.repositories.analytics_repository import AnalyticsRepository

logger = logging.getLogger(__name__)


class AnalyticsServiceError(Exception):
    """Base error for analytics service failures."""


class AnalyticsValidationError(AnalyticsServiceError):
    """Raised when analytics query input fails validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class MonthlyPlayCount:
    month: str
    plays: int


@dataclass(frozen=True)
class AnalyticsTopRecord:
    release: Releases
    plays: int
    average_rating: float | None


class AnalyticsService:
    def __init__(self, analytics_repository: AnalyticsRepository | None = None) -> None:
        self._analytics_repository = analytics_repository or AnalyticsRepository()

    def get_monthly_plays(self, db: Session) -> list[MonthlyPlayCount]:
        logger.info("Loading monthly analytics play counts")
        return [
            MonthlyPlayCount(month=str(month), plays=int(plays))
            for month, plays in self._analytics_repository.get_monthly_play_counts(db)
        ]

    def get_top_records(self, db: Session, *, limit: int = 10) -> list[AnalyticsTopRecord]:
        if limit < 1 or limit > 50:
            logger.info("Rejecting analytics top records invalid_limit=%s", limit)
            raise AnalyticsValidationError("invalid_limit", "limit must be between 1 and 50.")

        logger.info("Loading analytics top records limit=%s", limit)
        return [
            AnalyticsTopRecord(
                release=release,
                plays=int(plays),
                average_rating=float(average_rating) if average_rating is not None else None,
            )
            for release, plays, average_rating in self._analytics_repository.get_top_records(db, limit=limit)
        ]

    def get_rating_distribution(self, db: Session) -> dict[str, int]:
        logger.info("Loading analytics rating distribution")
        ratings = {str(rating): 0 for rating in range(1, 6)}
        for rating, plays in self._analytics_repository.get_rating_distribution(db):
            ratings[str(int(rating))] = int(plays)
        return ratings

    def get_mood_distribution(self, db: Session) -> dict[str, int]:
        logger.info("Loading analytics mood distribution")
        return {
            str(mood): int(plays)
            for mood, plays in self._analytics_repository.get_mood_distribution(db)
            if mood is not None and str(mood).strip()
        }
