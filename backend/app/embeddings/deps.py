from functools import lru_cache

from fastapi import HTTPException, status

from app.core.config import settings
from app.embeddings.base import EmbeddingConfigurationError, EmbeddingProvider
from app.embeddings.gemini import GeminiEmbeddingProvider


@lru_cache
def _configured_provider() -> EmbeddingProvider:
    if settings.EMBEDDING_PROVIDER == "gemini":
        return GeminiEmbeddingProvider(
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )
    raise EmbeddingConfigurationError("Unsupported embedding provider")


def get_embedding_provider() -> EmbeddingProvider:
    try:
        return _configured_provider()
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "EMBEDDING_NOT_CONFIGURED",
                "message": "Embedding service is not configured",
            },
        ) from exc
