"""Central metadata registry, required by Alembic."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models here so Alembic sees them
from app import models  # noqa
