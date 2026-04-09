import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def releases():
    logger.info("Releases endpoint called")

    return {"message": "list of releases"}
