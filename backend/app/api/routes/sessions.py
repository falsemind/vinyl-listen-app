import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/")
def log_session():
    logger.info("Sessions endpoint called")

    return {"message": "session logged"}
