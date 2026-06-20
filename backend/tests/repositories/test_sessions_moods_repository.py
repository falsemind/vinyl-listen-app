from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.auth import UserAccount
from app.models.sessions_moods import SessionsMoods
from app.repositories.sessions_moods_repository import SessionsMoodsRepository


def test_sessions_moods_repository_persists_custom_moods() -> None:
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
    SessionsMoods.__table__.create(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as db:
        created = SessionsMoodsRepository.create_custom(db, "Late Night", user_id="user-1")
        other_user_created = SessionsMoodsRepository.create_custom(db, "Late Night", user_id="user-2")

        assert created.name == "Late Night"
        assert other_user_created.name == "Late Night"
        assert SessionsMoodsRepository.get_by_name(db, "late night", user_id="user-1").id == created.id
        assert SessionsMoodsRepository.get_by_name(db, "late night", user_id="user-2").id == other_user_created.id
        assert [mood.name for mood in SessionsMoodsRepository.get_custom(db, user_id="user-1")] == ["Late Night"]

        assert SessionsMoodsRepository.delete_custom(db, "late night", user_id="user-1") is True
        assert SessionsMoodsRepository.get_custom(db, user_id="user-1") == []
        assert [mood.name for mood in SessionsMoodsRepository.get_custom(db, user_id="user-2")] == ["Late Night"]
