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
