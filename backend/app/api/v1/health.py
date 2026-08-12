from fastapi import APIRouter
from app.schemas.health import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """
    Health check endpoint.
    Used by monitoring services or frontend to check if the backend is alive.
    Returns a typed JSON response defined by HealthResponse.
    """
    return HealthResponse(
        status="ok",
        service="AURORA backend",
        version="0.1.0"
    )
