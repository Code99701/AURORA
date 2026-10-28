"""Comprehensive test suite for Phase 5D: Qwen3-Only LLM Architecture in AURORA."""

from collections.abc import AsyncIterator
import json
import uuid
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.embeddings.deps import get_embedding_provider
from app.llm.base import (
    GenerationResult,
    LLMConfigurationError,
    LLMProvider,
    LLMProviderError,
    StreamingGenerationEvent,
)
from app.llm.deps import get_llm_provider, _configured_llm_provider
from app.llm.ollama import OllamaLLMProvider
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.extracted_page import ExtractedPage
from app.models.workspace import Workspace
from app.services import rag as rag_service
from app.services.retrieval import RetrievedChunk


# ---------------------------------------------------------------------------
# Test Doubles and Mocks
# ---------------------------------------------------------------------------

class FakeEmbeddingProvider:
    provider_name = "fake"
    model_name = "fake-embedding"
    dimension = EMBEDDING_DIMENSION

    def embed_documents(self, texts):
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, text):
        return [0.0] * self.dimension


class ConfigurableMockOllama:
    def __init__(
        self,
        model_name: str = "qwen3:8b",
        response_text: str = "Answer from local Qwen3.",
        raise_on_generate: Exception | None = None,
        raise_on_stream: Exception | None = None,
    ):
        self.model_name = model_name
        self.provider_name = "ollama"
        self.response_text = response_text
        self.raise_on_generate = raise_on_generate
        self.raise_on_stream = raise_on_stream
        self.calls: list[tuple[str, str]] = []
        self.stream_calls: list[tuple[str, str]] = []

    def generate(self, system_instruction: str, user_prompt: str) -> GenerationResult:
        self.calls.append((system_instruction, user_prompt))
        if self.raise_on_generate:
            raise self.raise_on_generate
        return GenerationResult(self.response_text, f"ollama/{self.model_name}", "stop")

    async def stream_generate(
        self, system_instruction: str, user_prompt: str
    ) -> AsyncIterator[StreamingGenerationEvent]:
        self.stream_calls.append((system_instruction, user_prompt))
        if self.raise_on_stream:
            raise self.raise_on_stream
        yield StreamingGenerationEvent(event_type="text_delta", text=self.response_text)
        yield StreamingGenerationEvent(
            event_type="completion", model_name=f"ollama/{self.model_name}", finish_reason="stop"
        )


def authenticated_client(email: str) -> tuple[TestClient, dict]:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "aurora-phase5-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "aurora-phase5-password"},
    )
    assert login.status_code == 200
    return client, registration.json()


def create_workspace(client: TestClient, name: str = "Qwen3 Workspace") -> dict:
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_evidence_chunk(workspace_id: str, user_id: int, text: str = "Test chunk text", page: int = 1) -> RetrievedChunk:
    with SessionLocal() as db:
        document = Document(
            workspace_id=UUID(workspace_id),
            uploaded_by=user_id,
            original_filename="ai_ethics.pdf",
            storage_provider="test",
            storage_key=f"tests/{uuid.uuid4()}.pdf",
            content_type="application/pdf",
            file_size=300,
            checksum="f" * 64,
            status="PROCESSED",
            page_count=3,
            indexing_status="INDEXED",
            embedding_model="fake-embedding",
            embedding_dimension=EMBEDDING_DIMENSION,
        )
        db.add(document)
        db.flush()
        page_rec = ExtractedPage(
            document_id=document.id,
            page_number=page,
            text=text,
            character_count=len(text),
        )
        db.add(page_rec)
        db.flush()
        chunk = DocumentChunk(
            document_id=document.id,
            extracted_page_id=page_rec.id,
            page_number=page,
            chunk_index=0,
            page_chunk_index=0,
            text=text,
            character_count=len(text),
            approximate_token_count=12,
            embedding=[0.0] * EMBEDDING_DIMENSION,
            embedding_model="fake-embedding",
        )
        db.add(chunk)
        db.commit()
        return RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            filename=document.original_filename,
            page_number=page,
            text=chunk.text,
            similarity=0.95,
        )


# ---------------------------------------------------------------------------
# Architecture Tests
# ---------------------------------------------------------------------------

def test_qwen3_is_only_configured_llm_provider():
    """Verify that Qwen3 via Ollama is the sole configured LLM provider across settings and deps."""
    assert settings.LLM_PROVIDER == "ollama"
    assert settings.LLM_MODEL == "qwen3:8b"
    assert settings.OLLAMA_MODEL == "qwen3:8b"
    assert settings.OLLAMA_THINK is False

    provider = get_llm_provider()
    assert isinstance(provider, OllamaLLMProvider)
    assert provider.provider_name == "ollama"
    assert provider.model_name == "qwen3:8b"
    assert provider.think is False

    # Verify no Gemini API key is configured or required
    assert not hasattr(settings, "GEMINI_API_KEY")


def test_missing_ollama_service_returns_actionable_error(monkeypatch):
    """Verify that when Ollama is unreachable, an actionable error is raised without falling back."""
    provider = OllamaLLMProvider(base_url="http://127.0.0.1:11434", model_name="qwen3:8b")

    def mock_post(url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.Client, "post", lambda self, url, **kwargs: mock_post(url, **kwargs))

    with pytest.raises(LLMProviderError) as exc_info:
        provider.generate("System", "Prompt")
    assert "Ollama is not reachable at http://127.0.0.1:11434" in str(exc_info.value)
    assert "Ensure the Ollama server is running" in str(exc_info.value)


def test_missing_local_model_returns_actionable_error(monkeypatch):
    """Verify that when the requested model is not found, an actionable error instructs how to pull it."""
    provider = OllamaLLMProvider(base_url="http://127.0.0.1:11434", model_name="qwen3:8b")

    def mock_post(url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(404, request=req, json={"error": "model 'qwen3:8b' not found"})

    monkeypatch.setattr(httpx.Client, "post", lambda self, url, **kwargs: mock_post(url, **kwargs))

    with pytest.raises(LLMProviderError) as exc_info:
        provider.generate("System", "Prompt")
    assert "Ollama model 'qwen3:8b' was not found" in str(exc_info.value)
    assert "ollama pull qwen3:8b" in str(exc_info.value)


def test_ollama_payload_disables_thinking_by_default(monkeypatch):
    """Verify that thinking is disabled (think=False) in the request payload by default."""
    provider = OllamaLLMProvider(base_url="http://127.0.0.1:11434", model_name="qwen3:8b")
    assert provider.think is False

    captured_payload = None

    def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        req = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=req,
            json={
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": "Fast answer without thinking"},
                "done": True,
                "done_reason": "stop",
            },
        )

    monkeypatch.setattr(httpx.Client, "post", lambda self, url, **kwargs: mock_post(url, **kwargs))

    res = provider.generate("System", "Prompt")
    assert res.text == "Fast answer without thinking"
    assert captured_payload is not None
    assert captured_payload["think"] is False
    assert captured_payload["options"]["num_ctx"] == 8192 or captured_payload["options"]["num_ctx"] == 4096


def test_ollama_payload_respects_think_true_when_configured():
    """Verify that think=True is respected when explicitly configured."""
    provider = OllamaLLMProvider(
        base_url="http://127.0.0.1:11434", model_name="qwen3:8b", think=True
    )
    assert provider.think is True
    payload = provider._chat_payload("System", "Prompt", stream=False)
    assert payload["think"] is True


def test_rag_turn_with_qwen3_preserves_citations_and_provenance(monkeypatch):
    """Verify end-to-end RAG response generation via Qwen3 preserves citations and provenance."""
    client, user = authenticated_client("qwen3-e2e@example.com")
    workspace = create_workspace(client)
    evidence = create_evidence_chunk(
        workspace["id"],
        user["id"],
        text="Autonomous systems require strict safety and alignment verification.",
        page=2,
    )

    ollama = ConfigurableMockOllama(
        model_name="qwen3:8b",
        response_text="Safety and alignment verification is essential for autonomous systems.",
    )

    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: ollama

    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: [evidence]
    )

    try:
        response = client.post(
            f"/api/v1/workspaces/{workspace['id']}/rag",
            json={"query": "What do autonomous systems require?"},
        )
        assert response.status_code == 200
        data = response.json()

        # Answer was generated by Ollama
        assert "Safety and alignment verification" in data["answer"]
        assert data["model"] == "ollama/qwen3:8b"
        assert data["insufficient_evidence"] is False

        # Citations are intact and point to the authorized chunk on page 2
        assert len(data["sources"]) == 1
        assert data["sources"][0]["page_number"] == 2
        assert data["sources"][0]["filename"] == "ai_ethics.pdf"
        assert data["sources"][0]["chunk_id"] == str(evidence.chunk_id)

    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def test_multilingual_hindi_preference_preserved_with_qwen3(monkeypatch):
    """Verify that Hindi language preference is communicated to Qwen3."""
    client, user = authenticated_client("hindi-qwen3@example.com")
    workspace = create_workspace(client, "Hindi Workspace")
    evidence = create_evidence_chunk(
        workspace["id"],
        user["id"],
        text="Autonomous safety rules require strict verification.",
        page=1,
    )

    ollama = ConfigurableMockOllama(
        model_name="qwen3:8b",
        response_text="स्वचालित प्रणालियों को सख्त सुरक्षा की आवश्यकता होती है।",
    )

    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: [evidence]
    )

    with SessionLocal() as db:
        ws = db.get(Workspace, UUID(workspace["id"]))
        result = rag_service.answer_question(
            db=db,
            workspace=ws,
            requested_by=user["id"],
            query="Explain the rules",
            top_k=5,
            answer_language="Hindi",
            embedding_provider=FakeEmbeddingProvider(),
            llm_provider=ollama,
            persist_commit=False,
        )

        assert "स्वचालित" in result.answer
        assert result.model == "ollama/qwen3:8b"
        # Prompt passed to Ollama contained Hindi instruction
        assert len(ollama.calls) == 1
        assert "Answer language preference: Hindi" in ollama.calls[0][1]


def test_honest_refusal_when_insufficient_evidence(monkeypatch):
    """Verify honest refusal when evidence is insufficient without calling LLM."""
    client, user = authenticated_client("refusal-qwen3@example.com")
    workspace = create_workspace(client, "Refusal Workspace")

    ollama = ConfigurableMockOllama(
        model_name="qwen3:8b",
        response_text="Should never be called because evidence is empty.",
    )

    # Empty retrieval results
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: []
    )

    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: ollama

    try:
        response = client.post(
            f"/api/v1/workspaces/{workspace['id']}/rag",
            json={"query": "What is the secret formula?"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["insufficient_evidence"] is True
        assert len(data["sources"]) == 0
        assert len(ollama.calls) == 0  # LLM was never called!
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def test_workspace_isolation_enforced():
    """Verify that unauthorized user cannot query another workspace's RAG pipeline."""
    client_a, user_a = authenticated_client("user_a@example.com")
    client_b, user_b = authenticated_client("user_b@example.com")

    workspace_a = create_workspace(client_a, "Workspace A")

    # User B attempts to access Workspace A
    res = client_b.post(
        f"/api/v1/workspaces/{workspace_a['id']}/rag",
        json={"query": "Can I read this?"},
    )
    assert res.status_code == 404  # Workspace isolation returns 404 for non-members
