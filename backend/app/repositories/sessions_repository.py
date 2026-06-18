from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.models.sessions import Sessions, SessionTracks


class SessionsRepository:
    @staticmethod
    def get_by_id(db: Session, session_id: str) -> Sessions | None:
        return db.query(Sessions).filter(Sessions.id == session_id).one_or_none()

    @staticmethod
    def get_by_release_id(
        db: Session,
        release_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[Sessions]:
        return (
            db.query(Sessions)
            .filter(Sessions.release_id == release_id)
            .order_by(Sessions.played_at.desc(), Sessions.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_flow_insight_sessions(db: Session, *, since: datetime | None = None) -> list[Sessions]:
        played_time = func.coalesce(Sessions.played_at, Sessions.created_at)
        query = db.query(Sessions)
        if since is not None:
            query = query.filter(played_time >= since)
        return query.order_by(played_time.asc(), Sessions.created_at.asc()).all()

    @staticmethod
    def get_mood_by_name(db: Session, name: str) -> str | None:
        row = (
            db.query(Sessions.mood)
            .filter(Sessions.mood.isnot(None))
            .filter(Sessions.mood != "")
            .filter(func.lower(Sessions.mood) == name.lower())
            .order_by(Sessions.created_at.asc())
            .first()
        )
        return row[0] if row is not None else None

    @staticmethod
    def get_recent_with_releases(
        db: Session,
        *,
        limit: int,
    ):
        return (
            db.query(Sessions, Releases)
            .join(Releases, Sessions.release_id == Releases.id)
            .order_by(Sessions.played_at.desc(), Sessions.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_recent_notes_with_releases(
        db: Session,
        *,
        limit: int,
    ):
        return (
            db.query(Sessions, Releases)
            .join(Releases, Sessions.release_id == Releases.id)
            .filter(Sessions.notes.isnot(None))
            .filter(Sessions.notes != "")
            .order_by(Sessions.played_at.desc(), Sessions.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_all(db: Session) -> int:
        return db.query(func.count(Sessions.id)).scalar() or 0

    @staticmethod
    def get_latest_created_at_by_session_group_id(db: Session, session_group_id: str) -> datetime | None:
        return db.query(func.max(Sessions.created_at)).filter(Sessions.session_group_id == session_group_id).scalar()

    @staticmethod
    def count_distinct_releases_since(
        db: Session,
        *,
        since: datetime,
    ) -> int:
        return (
            db.query(func.count(func.distinct(Sessions.release_id))).filter(Sessions.played_at >= since).scalar() or 0
        )

    @staticmethod
    def get_top_release_stats(
        db: Session,
        *,
        limit: int,
    ):
        plays = func.count(Sessions.id).label("plays")
        average_rating = func.avg(Sessions.rating).label("average_rating")
        return (
            db.query(Releases, plays, average_rating)
            .join(Sessions, Sessions.release_id == Releases.id)
            .group_by(Releases.id)
            .order_by(plays.desc(), average_rating.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def create(
        db: Session,
        *,
        release_id: str,
        session_group_id: str | None,
        rating: int | None,
        mood: str | None,
        notes: str | None,
        played_at: datetime,
        vinyl_side: str | None,
    ) -> Sessions:
        session = Sessions(
            release_id=release_id,
            session_group_id=session_group_id,
            rating=rating,
            mood=mood,
            notes=notes,
            played_at=played_at,
            vinyl_side=vinyl_side,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def update(
        db: Session,
        session: Sessions,
        *,
        rating: int | None,
        mood: str | None,
        notes: str | None,
        vinyl_side: str | None,
    ) -> Sessions:
        session.rating = rating
        session.mood = mood
        session.notes = notes
        session.vinyl_side = vinyl_side
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def replace_tracks(
        db: Session,
        *,
        session_id: str,
        tracks: list[dict],
    ) -> list[SessionTracks]:
        db.query(SessionTracks).filter(SessionTracks.session_id == session_id).delete()
        session_tracks = [
            SessionTracks(
                session_id=session_id,
                track_position=track["position"],
                track_artist=track.get("artist"),
                track_title=track["title"],
                track_duration=track.get("duration"),
                track_sequence=track.get("sequence"),
            )
            for track in tracks
        ]
        db.add_all(session_tracks)
        db.commit()
        for track in session_tracks:
            db.refresh(track)
        return session_tracks

    @staticmethod
    def get_tracks_by_session_id(db: Session, session_id: str) -> list[SessionTracks]:
        return (
            db.query(SessionTracks)
            .filter(SessionTracks.session_id == session_id)
            .order_by(SessionTracks.track_sequence.asc(), SessionTracks.track_position.asc())
            .all()
        )

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
