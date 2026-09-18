from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.schemas.health import HealthResponse, DatabaseHealthResponse
from app.core.config import settings
from datetime import datetime, timezone
import logging
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def get_health():
    """
    Health check endpoint.
    Used by monitoring services or frontend to check if the backend is alive.
    """
    logger.info("Health check endpoint called")
    return HealthResponse(
        status="ok",
        service="AURORA backend",
        version="0.1.0"
    )

@router.get("/health/db", response_model=DatabaseHealthResponse)
def database_health_check(db: Session = Depends(get_db)):
    """
    Returns the status of the database connection.
    """
    try:
        # Perform a lightweight query to verify connectivity
        db.execute(text("SELECT 1"))
        return DatabaseHealthResponse(
            status="ok",
            database="connected"
        )
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
        )
