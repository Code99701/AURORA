from functools import lru_cache

from fastapi import HTTPException, status

from app.core.config import settings
from app.embeddings.base import EmbeddingConfigurationError, EmbeddingProvider
from app.embeddings.local import LocalEmbeddingProvider


@lru_cache
def _configured_provider() -> EmbeddingProvider:
    return LocalEmbeddingProvider(
        model_name=settings.LOCAL_EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
        device=settings.LOCAL_EMBEDDING_DEVICE,
        batch_size=settings.LOCAL_EMBEDDING_BATCH_SIZE,
        cache_size=settings.LOCAL_EMBEDDING_CACHE_SIZE,
    )


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


def warm_up_embedding_model() -> dict[str, str]:
    """Warm up the active embedding model if configured for local execution.

    Returns diagnostic status dict.
    Does not raise exceptions so application startup is not halted if local model load fails.
    """
    import logging

    log = logging.getLogger(__name__)

    if settings.EMBEDDING_PROVIDER != "local":
        return {"status": "skipped", "provider": settings.EMBEDDING_PROVIDER}

    try:
        provider = get_embedding_provider()
        if hasattr(provider, "warm_up"):
            provider.warm_up()
        log.info(
            "Local embedding model '%s' successfully warmed up (device: %s).",
            provider.model_name,
            getattr(provider, "device", "unknown"),
        )
        return {
            "status": "ready",
            "provider": provider.provider_name,
            "model": provider.model_name,
            "device": getattr(provider, "device", "unknown"),
        }
    except Exception as exc:
        log.error(
            "Failed to warm up local embedding model '%s': %s. "
            "Application startup will proceed, but embedding operations may fail until resolved.",
            settings.LOCAL_EMBEDDING_MODEL,
            exc,
            exc_info=True,
        )
        return {
            "status": "failed",
            "provider": settings.EMBEDDING_PROVIDER,
            "model": settings.LOCAL_EMBEDDING_MODEL,
            "error": str(exc),
        }
