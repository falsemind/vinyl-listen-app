import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def health_check():
    logger.info("Health endpoint called")

    return {"status": "ok"}
