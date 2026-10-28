from collections import OrderedDict
import hashlib
import logging
import threading
from typing import Any

from app.embeddings.base import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    validate_and_normalize,
)

logger = logging.getLogger(__name__)

# Global singleton storage for loaded SentenceTransformer models: (model_name, device) -> model
_MODEL_CACHE: dict[tuple[str, str], Any] = {}
_MODEL_LOCK = threading.Lock()


def resolve_embedding_device(requested_device: str | None = None) -> str:
    """Resolve the execution device, defaulting to CUDA when available, else CPU."""
    if requested_device and requested_device.strip():
        dev = requested_device.strip().lower()
        if dev == "cuda":
            import torch

            if not torch.cuda.is_available():
                logger.warning(
                    "CUDA was explicitly requested for local embeddings, but torch.cuda.is_available() is False. Falling back to CPU."
                )
                return "cpu"
        return dev

    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info("LocalEmbeddingProvider: CUDA detected (%s); using GPU acceleration.", gpu_name)
            return "cuda"
    except Exception as exc:
        logger.debug("LocalEmbeddingProvider: Device detection fallback to CPU (%s)", exc)

    return "cpu"


class LocalEmbeddingProvider:
    """Local multilingual embedding provider using SentenceTransformers (default: intfloat/multilingual-e5-base).

    Key architectural guarantees:
    - 768-dimensional output matching the PostgreSQL pgvector schema.
    - E5 prefix discipline: 'query: ' for search queries, 'passage: ' for document chunks.
    - Singleton model loading: weights are loaded once per process and shared across threads.
    - In-memory bounded LRU cache with model-isolated, prefix-isolated SHA-256 keys.
    - Automatic fallback to CPU when CUDA is unavailable.
    - Strict finite-value and dimension validation on every generated vector.
    """

    provider_name: str = "local"

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-base",
        dimension: int = 768,
        device: str | None = None,
        batch_size: int = 32,
        cache_size: int = 2048,
    ):
        if not model_name or not model_name.strip():
            raise EmbeddingConfigurationError("Local embedding model name must not be blank")
        if dimension != 768:
            raise EmbeddingConfigurationError(f"Local embedding dimension must be 768, got {dimension}")

        self.model_name = model_name.strip()
        self.dimension = dimension
        self.batch_size = max(1, batch_size)
        self.cache_size = max(0, cache_size)
        self.device = resolve_embedding_device(device)
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._model: Any = None

    def _get_model(self) -> Any:
        """Lazy singleton loader for the underlying SentenceTransformer model."""
        if self._model is not None:
            return self._model

        key = (self.model_name, self.device)
        with _MODEL_LOCK:
            if key in _MODEL_CACHE:
                self._model = _MODEL_CACHE[key]
                return self._model

            try:
                from sentence_transformers import SentenceTransformer

                logger.info(
                    "Loading local embedding model '%s' on device '%s'...",
                    self.model_name,
                    self.device,
                )
                model = SentenceTransformer(self.model_name, device=self.device)
                _MODEL_CACHE[key] = model
                self._model = model
                logger.info("Local embedding model '%s' loaded successfully.", self.model_name)
                return self._model
            except Exception as exc:
                logger.error(
                    "Failed to initialize local embedding model '%s' on device '%s': %s",
                    self.model_name,
                    self.device,
                    exc,
                )
                raise EmbeddingProviderError(
                    f"Failed to initialize local embedding model '{self.model_name}': {exc}"
                ) from exc

    def warm_up(self) -> None:
        """Preload the underlying SentenceTransformer model and execute a lightweight warm-up pass.

        Ensures weights, PyTorch compute kernels, and CUDA/CPU contexts are initialized.
        Safe to call multiple times; duplicate loads are prevented by the singleton cache.
        """
        model = self._get_model()
        dummy_text = "warmup"
        try:
            model.encode(
                [f"query: {dummy_text}"],
                batch_size=1,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            logger.info("Local embedding model '%s' warm-up pass completed.", self.model_name)
        except Exception as exc:
            logger.warning("Local embedding warm-up pass encountered an issue: %s", exc)

    def _build_cache_key(self, prefix: str, text: str) -> str:
        """Construct a collision-proof cache key scoped to model, dimension, and prefix."""
        normalized = " ".join(text.strip().split())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"{self.model_name}:{self.dimension}:{prefix}:{digest}"

    def _check_cache(self, key: str) -> list[float] | None:
        if self.cache_size <= 0:
            return None
        with self._cache_lock:
            vector = self._cache.get(key)
            if vector is not None:
                self._cache.move_to_end(key)
                return vector
        return None

    def _store_cache(self, key: str, vector: list[float]) -> None:
        if self.cache_size <= 0:
            return
        with self._cache_lock:
            self._cache[key] = vector
            self._cache.move_to_end(key)
            if len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)

    def _encode_texts(self, texts: list[str], prefix: str) -> list[list[float]]:
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        missing_indices: list[int] = []
        missing_texts_with_prefix: list[str] = []
        missing_keys: list[str] = []

        # Check cache first
        for i, text in enumerate(texts):
            key = self._build_cache_key(prefix, text)
            cached = self._check_cache(key)
            if cached is not None:
                results[i] = cached
            else:
                missing_indices.append(i)
                missing_texts_with_prefix.append(f"{prefix}{text}")
                missing_keys.append(key)

        if not missing_indices:
            return [vec for vec in results if vec is not None]

        # Inference for cache misses
        model = self._get_model()
        try:
            raw_embeddings = model.encode(
                missing_texts_with_prefix,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise EmbeddingProviderError(f"Local embedding inference failed: {exc}") from exc

        if len(raw_embeddings) != len(missing_indices):
            raise EmbeddingProviderError(
                f"Embedding output count mismatch: expected {len(missing_indices)}, got {len(raw_embeddings)}"
            )

        for idx, key, raw_vec in zip(missing_indices, missing_keys, raw_embeddings, strict=True):
            validated_vec = validate_and_normalize(raw_vec.tolist(), self.dimension)
            self._store_cache(key, validated_vec)
            results[idx] = validated_vec

        return [vec for vec in results if vec is not None]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of document chunks using the E5 'passage: ' prefix."""
        return self._encode_texts(texts, prefix="passage: ")

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query using the E5 'query: ' prefix."""
        results = self._encode_texts([text], prefix="query: ")
        if not results:
            raise EmbeddingProviderError("Failed to generate embedding for query")
        return results[0]
