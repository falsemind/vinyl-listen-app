import logging

from fastapi import APIRouter

from app.core.runtime_dependencies import get_runtime_dependency_statuses

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def health_check():
    logger.info("Health endpoint called")

    return {"status": "ok"}


@router.get("/runtime")
def runtime_health_check():
    logger.info("Runtime dependency health endpoint called")

    return {
        "status": "ok",
        "dependencies": [
            {
                "name": status.name,
                "available": status.available,
                "detail": status.detail,
            }
            for status in get_runtime_dependency_statuses()
        ],
    }
