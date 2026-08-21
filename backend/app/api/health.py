"""Healthcheck endpoint used by Docker healthchecks and monitoring."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db_session

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Returns 200 with DB connectivity status. Never raises to the caller."""
    settings = get_settings()
    db_status = "unknown"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001 - deliberately broad, this is a healthcheck
        logger.exception("Healthcheck DB connectivity failed: %s", exc)
        db_status = "error"

    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "database": db_status,
    }
