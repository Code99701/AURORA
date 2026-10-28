"""LLM provider dependencies for AURORA.

AURORA uses Ollama with local models (default: qwen3:8b) for 100% private,
on-device, reliable RAG generation.
"""

from functools import lru_cache
import logging

from fastapi import HTTPException, status

from app.core.config import settings
from app.llm.base import LLMConfigurationError, LLMProvider
from app.llm.ollama import OllamaLLMProvider

logger = logging.getLogger(__name__)


@lru_cache
def _configured_llm_provider() -> LLMProvider:
    return OllamaLLMProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model_name=settings.OLLAMA_MODEL,
        num_ctx=settings.OLLAMA_NUM_CTX,
        timeout_seconds=settings.OLLAMA_TIMEOUT_SECONDS,
        think=settings.OLLAMA_THINK,
    )


def get_llm_provider() -> LLMProvider:
    try:
        return _configured_llm_provider()
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "LLM_CONFIGURATION_ERROR",
                "message": "Generation service is not configured",
            },
        ) from exc
