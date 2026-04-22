import logging
import sys

from app.core.config import settings


def setup_logging():
    log_level_name = settings.log_level.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    for logger_name in (
        "app",
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "python_multipart",
        "sqlalchemy",
        "alembic",
    ):
        logging.getLogger(logger_name).setLevel(log_level)
