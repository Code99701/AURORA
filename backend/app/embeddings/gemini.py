import logging
import re
import time

import httpx

from app.embeddings.base import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    validate_and_normalize,
)


GEMINI_MAX_BATCH_SIZE = 100
GEMINI_MAX_ATTEMPTS = 6
GEMINI_MAX_RETRY_DELAY_SECONDS = 65.0
logger = logging.getLogger(__name__)


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return min(
                GEMINI_MAX_RETRY_DELAY_SECONDS,
                max(0.0, float(retry_after)),
            )
        except ValueError:
            pass
    try:
        message = str(response.json().get("error", {}).get("message", ""))
    except (ValueError, AttributeError):
        message = ""
    match = re.search(r"Please retry in ([0-9]+(?:\.[0-9]+)?)s", message)
    if match:
        return min(
            GEMINI_MAX_RETRY_DELAY_SECONDS,
            max(1.0, float(match.group(1)) + 1.0),
        )
    return min(GEMINI_MAX_RETRY_DELAY_SECONDS, float(2 ** (attempt - 1)))


class GeminiEmbeddingProvider:
    provider_name = "gemini"

    def __init__(self, api_key: str | None, model_name: str, dimension: int):
        if not api_key or not api_key.strip():
            raise EmbeddingConfigurationError("Gemini embedding API key is not configured")
        self.model_name = model_name
        self.dimension = dimension
        self._api_key = api_key.strip()

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        try:
            model_path = f"models/{self.model_name}"
            vectors: list[list[float]] = []
            for offset in range(0, len(texts), GEMINI_MAX_BATCH_SIZE):
                batch = texts[offset : offset + GEMINI_MAX_BATCH_SIZE]
                response: httpx.Response | None = None
                for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):
                    response = httpx.post(
                        "https://generativelanguage.googleapis.com/"
                        f"v1beta/{model_path}:batchEmbedContents",
                        headers={"x-goog-api-key": self._api_key},
                        json={
                            "requests": [
                                {
                                    "model": model_path,
                                    "content": {"parts": [{"text": text}]},
                                    "taskType": task_type,
                                    "outputDimensionality": self.dimension,
                                }
                                for text in batch
                            ]
                        },
                        timeout=30.0,
                    )
                    if response.status_code != 429:
                        break
                    if attempt == GEMINI_MAX_ATTEMPTS:
                        response.raise_for_status()
                    delay = _retry_delay_seconds(response, attempt)
                    logger.warning(
                        "Gemini embedding quota reached; retrying batch "
                        "(attempt=%s, batch_size=%s, delay=%.2fs)",
                        attempt,
                        len(batch),
                        delay,
                    )
                    time.sleep(delay)
                assert response is not None
                response.raise_for_status()
                embeddings = response.json().get("embeddings", [])
                if len(embeddings) != len(batch):
                    raise EmbeddingProviderError(
                        "Embedding provider returned an unexpected count"
                    )
                vectors.extend(
                    validate_and_normalize(
                        list(embedding.get("values", [])), self.dimension
                    )
                    for embedding in embeddings
                )
            return vectors
        except EmbeddingProviderError:
            raise
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Gemini embedding request rejected (status=%s)",
                exc.response.status_code,
            )
            raise EmbeddingProviderError("Embedding provider request failed") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Gemini embedding request could not reach provider (error=%s)",
                type(exc).__name__,
            )
            raise EmbeddingProviderError("Embedding provider request failed") from exc
        except Exception as exc:
            raise EmbeddingProviderError("Embedding provider request failed") from exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]
