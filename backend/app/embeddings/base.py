import math
from typing import Protocol


class EmbeddingConfigurationError(Exception):
    pass


class EmbeddingProviderError(Exception):
    pass


class EmbeddingDimensionError(EmbeddingProviderError):
    pass


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def validate_and_normalize(vector: list[float], dimension: int) -> list[float]:
    if len(vector) != dimension:
        raise EmbeddingDimensionError(
            f"Embedding dimension mismatch: expected {dimension}, received {len(vector)}"
        )
    try:
        values = [float(value) for value in vector]
    except (TypeError, ValueError) as exc:
        raise EmbeddingDimensionError("Embedding contains a non-numeric value") from exc
    if not all(math.isfinite(value) for value in values):
        raise EmbeddingDimensionError("Embedding contains a non-finite value")
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        raise EmbeddingDimensionError("Embedding vector has zero magnitude")
    return [value / magnitude for value in values]
