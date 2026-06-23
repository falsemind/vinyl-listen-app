import json
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.releases import ManualRelease, Releases
from app.models.sessions import Sessions, SessionTracks


@dataclass(frozen=True)
class AnalyticsReleaseSummary:
    id: str
    source: str
    discogs_release_id: int
    artist: str
    title: str
    year: int | None
    format: str | None
    label: str | None
    catalog_number: str | None
    genres: list[str] | None
    styles: list[str] | None
    thumbnail_url: str | None
    cover_image_url: str | None

    @property
    def target_key(self) -> str:
        return f"{self.source}:{self.id}"


class AnalyticsRepository:
    @staticmethod
    def get_monthly_play_counts(db: Session, *, user_id: str | None = None):
        month = AnalyticsRepository._month_expression(db)
        plays = func.count(Sessions.id).label("plays")
        query = db.query(month, plays).filter(Sessions.played_at.isnot(None))
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        return query.group_by(month).order_by(month.asc()).all()

    @staticmethod
    def get_sessions_for_month(
        db: Session,
        *,
        user_id: str | None = None,
        month: str,
        limit: int,
        offset: int,
    ) -> list[tuple[Sessions, AnalyticsReleaseSummary]]:
        month_expression = AnalyticsRepository._month_expression(db)
        query = db.query(Sessions, Releases).join(Releases, Sessions.release_id == Releases.id)
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        discogs_rows = (
            query.filter(Sessions.played_at.isnot(None))
            .filter(month_expression == month)
            .order_by(Sessions.played_at.desc(), Sessions.created_at.desc())
            .all()
        )
        manual_query = db.query(Sessions, ManualRelease).join(
            ManualRelease,
            Sessions.manual_release_id == ManualRelease.id,
        )
        if user_id is not None:
            manual_query = manual_query.filter(Sessions.user_id == user_id, ManualRelease.user_id == user_id)
        manual_rows = (
            manual_query.filter(Sessions.played_at.isnot(None))
            .filter(month_expression == month)
            .order_by(Sessions.played_at.desc(), Sessions.created_at.desc())
            .all()
        )
        rows = [
            (session, AnalyticsRepository._discogs_release_summary(release)) for session, release in discogs_rows
        ] + [(session, AnalyticsRepository._manual_release_summary(release)) for session, release in manual_rows]
        rows.sort(
            key=lambda item: (item[0].played_at, item[0].created_at),
            reverse=True,
        )
        return rows[offset : offset + limit]

    @staticmethod
    def get_tracks_by_session_ids(db: Session, session_ids: list[str]) -> dict[str, list[SessionTracks]]:
        if not session_ids:
            return {}

        rows = (
            db.query(SessionTracks)
            .filter(SessionTracks.session_id.in_(session_ids))
            .order_by(
                SessionTracks.session_id.asc(),
                SessionTracks.track_sequence.asc(),
                SessionTracks.track_position.asc(),
            )
            .all()
        )
        tracks_by_session_id: dict[str, list[SessionTracks]] = {}
        for track in rows:
            tracks_by_session_id.setdefault(track.session_id, []).append(track)
        return tracks_by_session_id

    @staticmethod
    def count_sessions_for_month(db: Session, *, month: str, user_id: str | None = None) -> int:
        month_expression = AnalyticsRepository._month_expression(db)
        query = db.query(func.count(Sessions.id)).filter(Sessions.played_at.isnot(None))
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        return query.filter(month_expression == month).scalar() or 0

    @staticmethod
    def get_top_records(db: Session, *, limit: int, user_id: str | None = None):
        plays = func.count(Sessions.id).label("plays")
        average_rating = func.avg(Sessions.rating).label("average_rating")
        query = db.query(Releases, plays, average_rating).join(Sessions, Sessions.release_id == Releases.id)
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        discogs_rows = query.group_by(Releases.id).all()
        manual_query = db.query(ManualRelease, plays, average_rating).join(
            Sessions,
            Sessions.manual_release_id == ManualRelease.id,
        )
        if user_id is not None:
            manual_query = manual_query.filter(Sessions.user_id == user_id, ManualRelease.user_id == user_id)
        manual_rows = manual_query.group_by(ManualRelease.id).all()
        rows = [
            (AnalyticsRepository._discogs_release_summary(release), int(row_plays), average_rating)
            for release, row_plays, average_rating in discogs_rows
        ] + [
            (AnalyticsRepository._manual_release_summary(release), int(row_plays), average_rating)
            for release, row_plays, average_rating in manual_rows
        ]
        rows.sort(
            key=lambda item: (
                -item[1],
                -(float(item[2]) if item[2] is not None else 0),
                item[0].artist.lower(),
                item[0].title.lower(),
            )
        )
        rows = rows[:limit]
        releases = [release for release, _plays, _average_rating in rows]
        top_tracks = AnalyticsRepository._get_top_tracks_by_release(db, releases, user_id=user_id)
        top_moods = AnalyticsRepository._get_top_moods_by_release(db, releases, user_id=user_id)
        return [
            (release, plays, average_rating, top_tracks.get(release.target_key), top_moods.get(release.target_key))
            for release, plays, average_rating in rows
        ]

    @staticmethod
    def get_records_for_rating(
        db: Session,
        *,
        user_id: str | None = None,
        rating: int,
        limit: int,
        offset: int,
    ) -> list[tuple[AnalyticsReleaseSummary, int]]:
        records = AnalyticsRepository._get_rating_record_counts(db, rating=rating, user_id=user_id)
        return records[offset : offset + limit]

    @staticmethod
    def count_records_for_rating(db: Session, *, rating: int, user_id: str | None = None) -> int:
        return len(AnalyticsRepository._get_rating_record_counts(db, rating=rating, user_id=user_id))

    @staticmethod
    def get_rating_distribution(db: Session, *, user_id: str | None = None):
        plays = func.count(Sessions.id).label("plays")
        query = db.query(Sessions.rating, plays).filter(Sessions.rating.isnot(None))
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        return query.group_by(Sessions.rating).order_by(Sessions.rating.asc()).all()

    @staticmethod
    def get_records_for_mood(
        db: Session,
        *,
        user_id: str | None = None,
        mood: str,
        limit: int,
        offset: int,
    ) -> list[tuple[AnalyticsReleaseSummary, int]]:
        records = AnalyticsRepository._get_mood_record_counts(db, mood=mood, user_id=user_id)
        return records[offset : offset + limit]

    @staticmethod
    def count_records_for_mood(db: Session, *, mood: str, user_id: str | None = None) -> int:
        return len(AnalyticsRepository._get_mood_record_counts(db, mood=mood, user_id=user_id))

    @staticmethod
    def get_mood_distribution(db: Session, *, user_id: str | None = None):
        query = db.query(Sessions.mood).filter(Sessions.mood.isnot(None)).filter(Sessions.mood != "")
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        mood_rows = query.all()
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
        user_id: str | None = None,
        style: str,
        limit: int,
        offset: int,
    ) -> list[tuple[AnalyticsReleaseSummary, int]]:
        records, _total = AnalyticsRepository.get_records_for_style_page(
            db,
            user_id=user_id,
            style=style,
            limit=limit,
            offset=offset,
        )
        return records

    @staticmethod
    def get_records_for_style_page(
        db: Session,
        *,
        user_id: str | None = None,
        style: str,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[AnalyticsReleaseSummary, int]], int]:
        records = AnalyticsRepository._get_style_record_counts(db, style=style, user_id=user_id)
        return records[offset : offset + limit], len(records)

    @staticmethod
    def count_records_for_style(db: Session, *, style: str, user_id: str | None = None) -> int:
        return len(AnalyticsRepository._get_style_record_counts(db, style=style, user_id=user_id))

    @staticmethod
    def get_style_distribution(db: Session, *, user_id: str | None = None):
        query = db.query(Releases.styles, Releases.genres).join(Sessions, Sessions.release_id == Releases.id)
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        style_rows = query.all()
        manual_query = db.query(ManualRelease.styles, ManualRelease.genres).join(
            Sessions,
            Sessions.manual_release_id == ManualRelease.id,
        )
        if user_id is not None:
            manual_query = manual_query.filter(Sessions.user_id == user_id, ManualRelease.user_id == user_id)
        style_rows += manual_query.all()
        style_counts: dict[str, tuple[str, int]] = {}
        for styles, genres in style_rows:
            for style in AnalyticsRepository._release_style_tags(styles, genres):
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
    def _get_style_record_counts(
        db: Session,
        *,
        style: str,
        user_id: str | None = None,
    ) -> list[tuple[AnalyticsReleaseSummary, int]]:
        target_style = AnalyticsRepository._normalized_label(style)
        if not target_style:
            return []

        query = db.query(Releases, Sessions.id).join(Sessions, Sessions.release_id == Releases.id)
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        style_rows = [
            (AnalyticsRepository._discogs_release_summary(release), session_id) for release, session_id in query.all()
        ]
        manual_query = db.query(ManualRelease, Sessions.id).join(
            Sessions,
            Sessions.manual_release_id == ManualRelease.id,
        )
        if user_id is not None:
            manual_query = manual_query.filter(Sessions.user_id == user_id, ManualRelease.user_id == user_id)
        style_rows += [
            (AnalyticsRepository._manual_release_summary(release), session_id)
            for release, session_id in manual_query.all()
        ]
        release_counts: dict[str, tuple[AnalyticsReleaseSummary, int]] = {}
        for release, _session_id in style_rows:
            if not AnalyticsRepository._styles_include(release.styles, release.genres, target_style):
                continue
            existing_release, count = release_counts.get(release.target_key, (release, 0))
            release_counts[release.target_key] = (existing_release, count + 1)

        return sorted(
            release_counts.values(),
            key=lambda item: (-item[1], item[0].artist.lower(), item[0].title.lower()),
        )

    @staticmethod
    def _get_top_tracks_by_release(
        db: Session,
        releases: list[AnalyticsReleaseSummary],
        *,
        user_id: str | None = None,
    ) -> dict[str, str]:
        if not releases:
            return {}

        discogs_ids = [release.id for release in releases if release.source == "discogs"]
        manual_ids = [release.id for release in releases if release.source == "manual"]
        rows: list[tuple[str, str | None]] = []
        query = db.query(Sessions.release_id, SessionTracks.track_title).join(
            SessionTracks,
            SessionTracks.session_id == Sessions.id,
        )
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        if discogs_ids:
            rows.extend(
                (f"discogs:{release_id}", track_title)
                for release_id, track_title in query.filter(Sessions.release_id.in_(discogs_ids))
                .filter(SessionTracks.track_title.isnot(None))
                .filter(func.trim(SessionTracks.track_title) != "")
                .all()
            )
        manual_query = db.query(Sessions.manual_release_id, SessionTracks.track_title).join(
            SessionTracks,
            SessionTracks.session_id == Sessions.id,
        )
        if user_id is not None:
            manual_query = manual_query.filter(Sessions.user_id == user_id)
        if manual_ids:
            rows.extend(
                (f"manual:{release_id}", track_title)
                for release_id, track_title in manual_query.filter(Sessions.manual_release_id.in_(manual_ids))
                .filter(SessionTracks.track_title.isnot(None))
                .filter(func.trim(SessionTracks.track_title) != "")
                .all()
            )
        track_counts: dict[str, dict[str, tuple[str, int]]] = {}
        for target_key, track_title in rows:
            canonical_title = track_title.strip()
            if not canonical_title:
                continue
            track_key = canonical_title.lower()
            release_counts = track_counts.setdefault(target_key, {})
            existing_title, count = release_counts.get(track_key, (canonical_title, 0))
            release_counts[track_key] = (existing_title, count + 1)

        return {
            target_key: sorted(counts.values(), key=lambda item: (-item[1], item[0].lower()))[0][0]
            for target_key, counts in track_counts.items()
            if counts
        }

    @staticmethod
    def _get_top_moods_by_release(
        db: Session,
        releases: list[AnalyticsReleaseSummary],
        *,
        user_id: str | None = None,
    ) -> dict[str, str]:
        if not releases:
            return {}

        discogs_ids = [release.id for release in releases if release.source == "discogs"]
        manual_ids = [release.id for release in releases if release.source == "manual"]
        rows: list[tuple[str, str | None]] = []
        query = db.query(Sessions.release_id, Sessions.mood)
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        if discogs_ids:
            rows.extend(
                (f"discogs:{release_id}", mood)
                for release_id, mood in query.filter(Sessions.release_id.in_(discogs_ids))
                .filter(Sessions.mood.isnot(None))
                .filter(func.trim(Sessions.mood) != "")
                .all()
            )
        manual_query = db.query(Sessions.manual_release_id, Sessions.mood)
        if user_id is not None:
            manual_query = manual_query.filter(Sessions.user_id == user_id)
        if manual_ids:
            rows.extend(
                (f"manual:{release_id}", mood)
                for release_id, mood in manual_query.filter(Sessions.manual_release_id.in_(manual_ids))
                .filter(Sessions.mood.isnot(None))
                .filter(func.trim(Sessions.mood) != "")
                .all()
            )
        mood_counts: dict[str, dict[str, tuple[str, int]]] = {}
        for target_key, mood in rows:
            canonical_mood = mood.strip()
            if not canonical_mood:
                continue
            mood_key = canonical_mood.lower()
            release_counts = mood_counts.setdefault(target_key, {})
            existing_mood, count = release_counts.get(mood_key, (canonical_mood, 0))
            release_counts[mood_key] = (existing_mood, count + 1)

        return {
            target_key: sorted(counts.values(), key=lambda item: (-item[1], item[0].lower()))[0][0]
            for target_key, counts in mood_counts.items()
            if counts
        }

    @staticmethod
    def _get_rating_record_counts(
        db: Session,
        *,
        rating: int,
        user_id: str | None = None,
    ) -> list[tuple[AnalyticsReleaseSummary, int]]:
        count = func.count(Sessions.id).label("count")
        query = db.query(Releases, count).join(Sessions, Sessions.release_id == Releases.id)
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        discogs_rows = query.filter(Sessions.rating == rating).group_by(Releases.id).all()
        manual_query = db.query(ManualRelease, count).join(Sessions, Sessions.manual_release_id == ManualRelease.id)
        if user_id is not None:
            manual_query = manual_query.filter(Sessions.user_id == user_id, ManualRelease.user_id == user_id)
        manual_rows = manual_query.filter(Sessions.rating == rating).group_by(ManualRelease.id).all()
        return AnalyticsRepository._sort_record_counts(
            [
                (AnalyticsRepository._discogs_release_summary(release), int(row_count))
                for release, row_count in discogs_rows
            ]
            + [
                (AnalyticsRepository._manual_release_summary(release), int(row_count))
                for release, row_count in manual_rows
            ]
        )

    @staticmethod
    def _get_mood_record_counts(
        db: Session,
        *,
        mood: str,
        user_id: str | None = None,
    ) -> list[tuple[AnalyticsReleaseSummary, int]]:
        count = func.count(Sessions.id).label("count")
        normalized_mood = AnalyticsRepository._normalized_label(mood)
        query = db.query(Releases, count).join(Sessions, Sessions.release_id == Releases.id)
        if user_id is not None:
            query = query.filter(Sessions.user_id == user_id)
        discogs_rows = (
            query.filter(Sessions.mood.isnot(None))
            .filter(func.lower(func.trim(Sessions.mood)) == normalized_mood)
            .group_by(Releases.id)
            .all()
        )
        manual_query = db.query(ManualRelease, count).join(Sessions, Sessions.manual_release_id == ManualRelease.id)
        if user_id is not None:
            manual_query = manual_query.filter(Sessions.user_id == user_id, ManualRelease.user_id == user_id)
        manual_rows = (
            manual_query.filter(Sessions.mood.isnot(None))
            .filter(func.lower(func.trim(Sessions.mood)) == normalized_mood)
            .group_by(ManualRelease.id)
            .all()
        )
        return AnalyticsRepository._sort_record_counts(
            [
                (AnalyticsRepository._discogs_release_summary(release), int(row_count))
                for release, row_count in discogs_rows
            ]
            + [
                (AnalyticsRepository._manual_release_summary(release), int(row_count))
                for release, row_count in manual_rows
            ]
        )

    @staticmethod
    def _sort_record_counts(
        records: list[tuple[AnalyticsReleaseSummary, int]],
    ) -> list[tuple[AnalyticsReleaseSummary, int]]:
        return sorted(
            records,
            key=lambda item: (-item[1], item[0].artist.lower(), item[0].title.lower()),
        )

    @staticmethod
    def _discogs_release_summary(release: Releases) -> AnalyticsReleaseSummary:
        return AnalyticsReleaseSummary(
            id=release.id,
            source="discogs",
            discogs_release_id=release.discogs_release_id,
            artist=release.artist,
            title=release.title,
            year=release.year,
            format=release.format,
            label=release.label,
            catalog_number=release.catalog_number,
            genres=release.genres,
            styles=AnalyticsRepository._release_style_tags(release.styles, release.genres),
            thumbnail_url=release.thumbnail_url,
            cover_image_url=release.cover_image_url,
        )

    @staticmethod
    def _manual_release_summary(release: ManualRelease) -> AnalyticsReleaseSummary:
        return AnalyticsReleaseSummary(
            id=release.id,
            source="manual",
            discogs_release_id=0,
            artist=release.artist,
            title=release.title,
            year=release.year,
            format=release.format,
            label=release.label,
            catalog_number=release.catalog_number,
            genres=release.genres,
            styles=AnalyticsRepository._release_style_tags(release.styles, release.genres),
            thumbnail_url=release.cover_thumbnail_url,
            cover_image_url=release.cover_image_url,
        )

    @staticmethod
    def _styles_include(styles, genres, target_style: str) -> bool:
        return any(
            AnalyticsRepository._normalized_label(style) == target_style
            for style in AnalyticsRepository._release_style_tags(styles, genres)
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
    def _release_style_tags(styles, genres) -> list[str]:
        parsed_styles = AnalyticsRepository._release_styles(styles)
        if parsed_styles:
            return parsed_styles
        return AnalyticsRepository._release_styles(genres)

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
