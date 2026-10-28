from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.embeddings.base import EmbeddingProviderError
from app.embeddings.deps import _configured_provider, get_embedding_provider, warm_up_embedding_model
from app.embeddings.local import _MODEL_CACHE, LocalEmbeddingProvider
from app.main import create_app


def test_warmup_during_lifespan_success():
    """Verify that startup lifespan runs embedding warm-up and keeps health check operational."""
    app = create_app()
    with TestClient(app) as client:
        # Check health check works
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        # Check app state has warm-up status
        assert hasattr(app.state, "embedding_warmup")
        status = app.state.embedding_warmup
        assert status["status"] in ("ready", "skipped")


def test_model_reuse_no_duplicate_instances():
    """Verify that multiple warm_up calls reuse the singleton cached model without reloading."""
    provider = LocalEmbeddingProvider(
        model_name="intfloat/multilingual-e5-base",
        dimension=768,
        device="cpu",
    )

    # First warm-up
    provider.warm_up()
    cache_key = (provider.model_name, provider.device)
    assert cache_key in _MODEL_CACHE
    initial_model = _MODEL_CACHE[cache_key]

    # Second warm-up call on the same provider
    provider.warm_up()
    assert _MODEL_CACHE[cache_key] is initial_model

    # A new provider instance pointing to the same model/device must reuse the cached model
    provider_2 = LocalEmbeddingProvider(
        model_name="intfloat/multilingual-e5-base",
        dimension=768,
        device="cpu",
    )
    model_2 = provider_2._get_model()
    assert model_2 is initial_model


def test_warmup_failure_handled_gracefully():
    """Verify that model initialization failures during warm-up log an error and do not halt app startup."""
    with patch("app.embeddings.deps.get_embedding_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.warm_up.side_effect = EmbeddingProviderError("Simulated disk error or missing weights")
        mock_get_provider.return_value = mock_provider

        result = warm_up_embedding_model()

        assert result["status"] == "failed"
        assert "Simulated disk error" in result["error"]

    # Test that app lifespan handles the failure and health endpoint remains functional
    with patch("app.main.warm_up_embedding_model") as mock_warmup:
        mock_warmup.return_value = {
            "status": "failed",
            "provider": "local",
            "model": "intfloat/multilingual-e5-base",
            "error": "Failed to load weights",
        }
        app = create_app()
        with TestClient(app) as client:
            res = client.get("/api/v1/health")
            assert res.status_code == 200
            assert res.json()["status"] == "ok"
            assert app.state.embedding_warmup["status"] == "failed"


def test_warmup_skipped_for_non_local_provider():
    """Verify that warm_up_embedding_model skips when EMBEDDING_PROVIDER is not local."""
    with patch.object(settings, "EMBEDDING_PROVIDER", "mock_external"):
        result = warm_up_embedding_model()
        assert result["status"] == "skipped"
        assert result["provider"] == "mock_external"
