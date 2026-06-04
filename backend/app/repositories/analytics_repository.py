import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.models.sessions import Sessions


class AnalyticsRepository:
    @staticmethod
    def get_monthly_play_counts(db: Session):
        month = AnalyticsRepository._month_expression(db)
        plays = func.count(Sessions.id).label("plays")
        return db.query(month, plays).filter(Sessions.played_at.isnot(None)).group_by(month).order_by(month.asc()).all()

    @staticmethod
    def get_sessions_for_month(
        db: Session,
        *,
        month: str,
        limit: int,
        offset: int,
    ) -> list[tuple[Sessions, Releases]]:
        month_expression = AnalyticsRepository._month_expression(db)
        return (
            db.query(Sessions, Releases)
            .join(Releases, Sessions.release_id == Releases.id)
            .filter(Sessions.played_at.isnot(None))
            .filter(month_expression == month)
            .order_by(Sessions.played_at.desc(), Sessions.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_sessions_for_month(db: Session, *, month: str) -> int:
        month_expression = AnalyticsRepository._month_expression(db)
        return (
            db.query(func.count(Sessions.id))
            .filter(Sessions.played_at.isnot(None))
            .filter(month_expression == month)
            .scalar()
            or 0
        )

    @staticmethod
    def get_top_records(db: Session, *, limit: int):
        plays = func.count(Sessions.id).label("plays")
        average_rating = func.avg(Sessions.rating).label("average_rating")
        return (
            db.query(Releases, plays, average_rating)
            .join(Sessions, Sessions.release_id == Releases.id)
            .group_by(Releases.id)
            .order_by(plays.desc(), Releases.artist.asc(), Releases.title.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_records_for_rating(
        db: Session,
        *,
        rating: int,
        limit: int,
        offset: int,
    ) -> list[tuple[Releases, int]]:
        count = func.count(Sessions.id).label("count")
        return (
            db.query(Releases, count)
            .join(Sessions, Sessions.release_id == Releases.id)
            .filter(Sessions.rating == rating)
            .group_by(Releases.id)
            .order_by(count.desc(), Releases.artist.asc(), Releases.title.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_records_for_rating(db: Session, *, rating: int) -> int:
        return (
            db.query(Releases.id)
            .join(Sessions, Sessions.release_id == Releases.id)
            .filter(Sessions.rating == rating)
            .group_by(Releases.id)
            .count()
        )

    @staticmethod
    def get_rating_distribution(db: Session):
        plays = func.count(Sessions.id).label("plays")
        return (
            db.query(Sessions.rating, plays)
            .filter(Sessions.rating.isnot(None))
            .group_by(Sessions.rating)
            .order_by(Sessions.rating.asc())
            .all()
        )

    @staticmethod
    def get_records_for_mood(
        db: Session,
        *,
        mood: str,
        limit: int,
        offset: int,
    ) -> list[tuple[Releases, int]]:
        count = func.count(Sessions.id).label("count")
        normalized_mood = AnalyticsRepository._normalized_label(mood)
        return (
            db.query(Releases, count)
            .join(Sessions, Sessions.release_id == Releases.id)
            .filter(Sessions.mood.isnot(None))
            .filter(func.lower(func.trim(Sessions.mood)) == normalized_mood)
            .group_by(Releases.id)
            .order_by(count.desc(), Releases.artist.asc(), Releases.title.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_records_for_mood(db: Session, *, mood: str) -> int:
        normalized_mood = AnalyticsRepository._normalized_label(mood)
        return (
            db.query(Releases.id)
            .join(Sessions, Sessions.release_id == Releases.id)
            .filter(Sessions.mood.isnot(None))
            .filter(func.lower(func.trim(Sessions.mood)) == normalized_mood)
            .group_by(Releases.id)
            .count()
        )

    @staticmethod
    def get_mood_distribution(db: Session):
        mood_rows = db.query(Sessions.mood).filter(Sessions.mood.isnot(None)).filter(Sessions.mood != "").all()
        mood_counts: dict[str, tuple[str, int]] = {}
        for (mood,) in mood_rows:
            canonical_mood = mood.strip()
            if not canonical_mood:
                continue
            mood_key = canonical_mood.lower()
            existing_mood, count = mood_counts.get(mood_key, (canonical_mood, 0))
            mood_counts[mood_key] = (existing_mood, count + 1)
        return sorted(mood_counts.values(), key=lambda item: (-item[1], item[0].lower()))

    @staticmethod
    def get_records_for_style(
        db: Session,
        *,
        style: str,
        limit: int,
        offset: int,
    ) -> list[tuple[Releases, int]]:
        return AnalyticsRepository._get_style_record_counts(db, style=style)[offset : offset + limit]

    @staticmethod
    def count_records_for_style(db: Session, *, style: str) -> int:
        return len(AnalyticsRepository._get_style_record_counts(db, style=style))

    @staticmethod
    def get_style_distribution(db: Session):
        style_rows = (
            db.query(Releases.styles)
            .join(Sessions, Sessions.release_id == Releases.id)
            .filter(Releases.styles.isnot(None))
            .all()
        )
        style_counts: dict[str, tuple[str, int]] = {}
        for (styles,) in style_rows:
            for style in AnalyticsRepository._release_styles(styles):
                style_key = style.lower()
                existing_style, count = style_counts.get(style_key, (style, 0))
                style_counts[style_key] = (existing_style, count + 1)
        return sorted(style_counts.values(), key=lambda item: (-item[1], item[0].lower()))

    @staticmethod
    def _month_expression(db: Session):
        dialect_name = db.get_bind().dialect.name
        if dialect_name == "sqlite":
            return func.strftime("%Y-%m", Sessions.played_at).label("month")

        return func.to_char(Sessions.played_at, "YYYY-MM").label("month")

    @staticmethod
    def _get_style_record_counts(db: Session, *, style: str) -> list[tuple[Releases, int]]:
        target_style = AnalyticsRepository._normalized_label(style)
        if not target_style:
            return []

        style_rows = (
            db.query(Releases, Sessions.id)
            .join(Sessions, Sessions.release_id == Releases.id)
            .filter(Releases.styles.isnot(None))
            .all()
        )
        release_counts: dict[str, tuple[Releases, int]] = {}
        for release, _session_id in style_rows:
            if not AnalyticsRepository._styles_include(release.styles, target_style):
                continue
            existing_release, count = release_counts.get(release.id, (release, 0))
            release_counts[release.id] = (existing_release, count + 1)

        return sorted(
            release_counts.values(),
            key=lambda item: (-item[1], item[0].artist.lower(), item[0].title.lower()),
        )

    @staticmethod
    def _styles_include(styles, target_style: str) -> bool:
        return any(
            AnalyticsRepository._normalized_label(style) == target_style
            for style in AnalyticsRepository._release_styles(styles)
        )

    @staticmethod
    def _normalized_label(value: str) -> str:
        return value.strip().lower()

    @staticmethod
    def _release_styles(styles) -> list[str]:
        if styles is None:
            return []
        parsed_styles = AnalyticsRepository._parse_serialized_styles(styles) if isinstance(styles, str) else styles
        return [str(style).strip() for style in parsed_styles if style is not None and str(style).strip()]

    @staticmethod
    def _parse_serialized_styles(styles: str) -> list[str]:
        stripped_styles = styles.strip()
        if not stripped_styles:
            return []
        try:
            parsed_styles = json.loads(stripped_styles)
        except json.JSONDecodeError:
            return [style.strip() for style in stripped_styles.split(",")]
        if isinstance(parsed_styles, list):
            return [str(style) for style in parsed_styles]
        return []
