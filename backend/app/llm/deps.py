from functools import lru_cache

from fastapi import HTTPException, status

from app.core.config import settings
from app.llm.base import LLMConfigurationError, LLMProvider
from app.llm.gemini import GeminiLLMProvider


@lru_cache
def _configured_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "gemini":
        return GeminiLLMProvider(
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.LLM_MODEL,
            max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        )
    raise LLMConfigurationError("Unsupported generation provider")


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
