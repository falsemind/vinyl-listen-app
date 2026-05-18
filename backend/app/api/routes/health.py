import logging

from fastapi import APIRouter

from app.core.config import settings
from app.core.runtime_dependencies import get_runtime_dependency_statuses
from app.database.db import SessionLocal
from app.repositories.identify_job_repository import IdentifyJobRepository
from app.services.identify_job_service import ACTIVE_IDENTIFY_JOB_STATUSES

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
        "operations": {
            "rate_limiter": {
                "enabled": settings.inbound_rate_limit_enabled,
                "backend": settings.inbound_rate_limit_backend,
            },
            "identify": get_identify_operations_status(),
        },
    }


def get_identify_operations_status() -> dict[str, int | None]:
    active_jobs: int | None
    try:
        with SessionLocal() as db:
            active_jobs = IdentifyJobRepository.count_active(
                db,
                active_statuses=ACTIVE_IDENTIFY_JOB_STATUSES,
            )
    except Exception:
        logger.warning("Unable to load identify operation status", exc_info=True)
        active_jobs = None

    return {
        "max_concurrency": settings.identify_max_concurrent_jobs,
        "active_jobs": active_jobs,
        "queued_jobs": None,
    }
