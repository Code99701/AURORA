import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.router import api_router

# Initialize logging for the application
setup_logging()
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """
    Application factory to create and configure the FastAPI app instance.
    This pattern makes testing easier and keeps configuration modular.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="AURORA Multilingual RAG Platform API",
        # Disable default docs in production, enable in development
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    # Configure CORS (Cross-Origin Resource Sharing)
    # This allows the frontend (e.g. Next.js on localhost:3000) to communicate with the backend
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Include the main API router under the configured API prefix (e.g., "/api/v1")
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Global Exception Handler
    # This ensures that any unhandled exception results in a structured JSON response
    # rather than exposing a stack trace to the client.
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"}
        )

    return app

app = create_app()
