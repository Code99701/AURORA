from fastapi import APIRouter
from app.api.v1 import health

# Main router for all v1 API endpoints
api_router = APIRouter()

# Include the health router
api_router.include_router(health.router, tags=["health"])
