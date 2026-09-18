from fastapi import APIRouter
from app.api.v1 import auth, conversations, documents, health, rag, retrieval, workspaces

# Main router for all v1 API endpoints
api_router = APIRouter()

# Include the health router
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(documents.router, prefix="/workspaces", tags=["documents"])
api_router.include_router(retrieval.router, prefix="/workspaces", tags=["retrieval"])
api_router.include_router(rag.router, prefix="/workspaces", tags=["rag"])
api_router.include_router(
    conversations.router, prefix="/workspaces", tags=["conversations"]
)
