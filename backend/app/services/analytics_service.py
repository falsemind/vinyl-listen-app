import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.releases import Releases
from app.models.sessions import Sessions
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
    top_track: str | None
    top_mood: str | None


@dataclass(frozen=True)
class AnalyticsPagination:
    limit: int
    offset: int
    total: int
    has_more: bool


@dataclass(frozen=True)
class AnalyticsSession:
    session: Sessions
    release: Releases


@dataclass(frozen=True)
class AnalyticsSessionPage:
    sessions: list[AnalyticsSession]
    pagination: AnalyticsPagination


@dataclass(frozen=True)
class AnalyticsRecordCount:
    release: Releases
    count: int


@dataclass(frozen=True)
class AnalyticsRecordCountPage:
    records: list[AnalyticsRecordCount]
    pagination: AnalyticsPagination


class AnalyticsService:
    def __init__(
        self,
        analytics_repository: AnalyticsRepository | None = None,
        max_page_limit: int | None = None,
    ) -> None:
        self._analytics_repository = analytics_repository or AnalyticsRepository()
        self._max_page_limit = max_page_limit or settings.max_page_limit

    def get_monthly_plays(self, db: Session) -> list[MonthlyPlayCount]:
        logger.info("Loading monthly analytics play counts")
        return [
            MonthlyPlayCount(month=str(month), plays=int(plays))
            for month, plays in self._analytics_repository.get_monthly_play_counts(db)
        ]

    def get_top_records(self, db: Session, *, limit: int = 10) -> list[AnalyticsTopRecord]:
        self._validate_limit(limit)

        logger.info("Loading analytics top records limit=%s", limit)
        return [
            AnalyticsTopRecord(
                release=release,
                plays=int(plays),
                average_rating=float(average_rating) if average_rating is not None else None,
                top_track=top_track,
                top_mood=top_mood,
            )
            for release, plays, average_rating, top_track, top_mood in self._analytics_repository.get_top_records(
                db,
                limit=limit,
            )
        ]

    def get_sessions_for_month(
        self,
        db: Session,
        *,
        month: str,
        limit: int = 10,
        offset: int = 0,
    ) -> AnalyticsSessionPage:
        normalized_month = self._validate_month(month)
        self._validate_pagination(limit=limit, offset=offset)

        logger.info("Loading analytics month sessions month=%s limit=%s offset=%s", normalized_month, limit, offset)
        rows = self._analytics_repository.get_sessions_for_month(
            db,
            month=normalized_month,
            limit=limit,
            offset=offset,
        )
        total = self._analytics_repository.count_sessions_for_month(db, month=normalized_month)
        sessions = [AnalyticsSession(session=session, release=release) for session, release in rows]
        return AnalyticsSessionPage(
            sessions=sessions,
            pagination=self._pagination(limit=limit, offset=offset, total=total, item_count=len(sessions)),
        )

    def get_records_for_rating(
        self,
        db: Session,
        *,
        rating: int,
        limit: int = 10,
        offset: int = 0,
    ) -> AnalyticsRecordCountPage:
        self._validate_rating(rating)
        self._validate_pagination(limit=limit, offset=offset)

        logger.info("Loading analytics rating records rating=%s limit=%s offset=%s", rating, limit, offset)
        rows = self._analytics_repository.get_records_for_rating(db, rating=rating, limit=limit, offset=offset)
        total = self._analytics_repository.count_records_for_rating(db, rating=rating)
        records = [AnalyticsRecordCount(release=release, count=int(count)) for release, count in rows]
        return AnalyticsRecordCountPage(
            records=records,
            pagination=self._pagination(limit=limit, offset=offset, total=total, item_count=len(records)),
        )

    def get_records_for_mood(
        self,
        db: Session,
        *,
        mood: str,
        limit: int = 10,
        offset: int = 0,
    ) -> AnalyticsRecordCountPage:
        normalized_mood = self._validate_label(mood, field="mood")
        self._validate_pagination(limit=limit, offset=offset)

        logger.info("Loading analytics mood records mood=%s limit=%s offset=%s", normalized_mood, limit, offset)
        rows = self._analytics_repository.get_records_for_mood(
            db,
            mood=normalized_mood,
            limit=limit,
            offset=offset,
        )
        total = self._analytics_repository.count_records_for_mood(db, mood=normalized_mood)
        records = [AnalyticsRecordCount(release=release, count=int(count)) for release, count in rows]
        return AnalyticsRecordCountPage(
            records=records,
            pagination=self._pagination(limit=limit, offset=offset, total=total, item_count=len(records)),
        )

    def get_records_for_style(
        self,
        db: Session,
        *,
        style: str,
        limit: int = 10,
        offset: int = 0,
    ) -> AnalyticsRecordCountPage:
        normalized_style = self._validate_label(style, field="style")
        self._validate_pagination(limit=limit, offset=offset)

        logger.info("Loading analytics style records style=%s limit=%s offset=%s", normalized_style, limit, offset)
        rows, total = self._analytics_repository.get_records_for_style_page(
            db,
            style=normalized_style,
            limit=limit,
            offset=offset,
        )
        records = [AnalyticsRecordCount(release=release, count=int(count)) for release, count in rows]
        return AnalyticsRecordCountPage(
            records=records,
            pagination=self._pagination(limit=limit, offset=offset, total=total, item_count=len(records)),
        )

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

    def get_style_distribution(self, db: Session) -> dict[str, int]:
        logger.info("Loading analytics style distribution")
        return {
            str(style): int(plays)
            for style, plays in self._analytics_repository.get_style_distribution(db)
            if style is not None and str(style).strip()
        }

    @staticmethod
    def _validate_month(month: str) -> str:
        normalized_month = month.strip()
        if (
            len(normalized_month) != 7
            or normalized_month[4] != "-"
            or not normalized_month[:4].isdigit()
            or not normalized_month[5:].isdigit()
            or not 1 <= int(normalized_month[5:]) <= 12
        ):
            raise AnalyticsValidationError("invalid_month", "month must use YYYY-MM format.")
        return normalized_month

    @staticmethod
    def _validate_rating(rating: int) -> None:
        if rating < 1 or rating > 5:
            raise AnalyticsValidationError("invalid_rating", "rating must be between 1 and 5.")

    @staticmethod
    def _validate_label(value: str, *, field: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise AnalyticsValidationError(f"invalid_{field}", f"{field} must not be blank.")
        return normalized_value

    def _validate_pagination(self, *, limit: int, offset: int) -> None:
        self._validate_limit(limit)
        if offset < 0:
            raise AnalyticsValidationError("invalid_offset", "offset cannot be negative.")

    def _validate_limit(self, limit: int) -> None:
        if limit < 1 or limit > self._max_page_limit:
            raise AnalyticsValidationError("invalid_limit", f"limit must be between 1 and {self._max_page_limit}.")

    @staticmethod
    def _pagination(*, limit: int, offset: int, total: int, item_count: int) -> AnalyticsPagination:
        return AnalyticsPagination(
            limit=limit,
            offset=offset,
            total=total,
            has_more=offset + item_count < total,
        )
