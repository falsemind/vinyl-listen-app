"""This creates one DB session per request. FastAPI automatically closes it after the request completes."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.database.db import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
