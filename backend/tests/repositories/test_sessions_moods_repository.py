from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.sessions_moods import SessionsMoods
from app.repositories.sessions_moods_repository import SessionsMoodsRepository


def test_sessions_moods_repository_persists_custom_moods() -> None:
    engine = create_engine("sqlite:///:memory:")
    SessionsMoods.__table__.create(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as db:
        created = SessionsMoodsRepository.create_custom(db, "Late Night")

        assert created.name == "Late Night"
        assert SessionsMoodsRepository.get_by_name(db, "late night").id == created.id
        assert [mood.name for mood in SessionsMoodsRepository.get_custom(db)] == ["Late Night"]

        assert SessionsMoodsRepository.delete_custom(db, "late night") is True
        assert SessionsMoodsRepository.get_custom(db) == []
