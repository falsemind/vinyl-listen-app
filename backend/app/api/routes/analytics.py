import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def analytics():
    logger.info("Analytics endpoint called")

    return {"message": "Some analytics insight"}
