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
    dependencies = get_runtime_dependency_statuses()
    unavailable_required = tuple(
        status for status in dependencies if not status.available and status.warn_when_unavailable
    )

    return {
        "status": "ok" if not unavailable_required else "degraded",
        "ready": not unavailable_required,
        "dependencies": [
            {
                "name": status.name,
                "available": status.available,
                "detail": status.detail,
                "required": status.warn_when_unavailable,
            }
            for status in dependencies
        ],
    }
