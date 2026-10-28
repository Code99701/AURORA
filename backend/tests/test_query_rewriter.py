"""Tests for Phase 4: Context-Aware Query Rewriting & Multi-Turn RAG in AURORA."""

from dataclasses import dataclass
import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.embeddings.deps import get_embedding_provider
from app.llm.base import (
    GenerationResult,
    LLMProvider,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
)
from app.llm.deps import get_llm_provider
from app.main import app
from app.models.conversation import Conversation, ConversationMessage
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.extracted_page import ExtractedPage
from app.models.workspace import WorkspaceMembership
from app.rag.rewriter import (
    RewriteResult,
    extract_core_subject,
    extract_numbered_items,
    get_last_turns,
    rewrite_query_for_retrieval,
)
from app.services import conversation as conversation_service
from app.services import rag as rag_service
from app.services.retrieval import RetrievedChunk


# ---------------------------------------------------------------------------
# Test Mocks and Helpers
# ---------------------------------------------------------------------------

class FakeEmbeddingProvider:
    provider_name = "fake"
    model_name = "fake-embedding"
    dimension = EMBEDDING_DIMENSION

    def embed_documents(self, texts):
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, text):
        return [0.0] * self.dimension


class MockLLMProvider:
    provider_name = "mock-llm"
    model_name = "mock-qwen3"

    def __init__(self, response_text: str = "Mock answer text", raise_exc: Exception | None = None):
        self.response_text = response_text
        self.raise_exc = raise_exc
        self.calls: list[tuple[str, str]] = []

    def generate(self, system_instruction: str, user_prompt: str) -> GenerationResult:
        self.calls.append((system_instruction, user_prompt))
        if self.raise_exc:
            raise self.raise_exc
        return GenerationResult(self.response_text, self.model_name, "STOP")

    async def stream_generate(self, system_instruction: str, user_prompt: str):
        from app.llm.base import StreamingGenerationEvent
        self.calls.append((system_instruction, user_prompt))
        if self.raise_exc:
            raise self.raise_exc
        yield StreamingGenerationEvent(event_type="text_delta", text=self.response_text)
        yield StreamingGenerationEvent(event_type="completion", model_name=self.model_name)


def authenticated_client(email: str) -> tuple[TestClient, dict]:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "aurora-phase4-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "aurora-phase4-password"},
    )
    assert login.status_code == 200
    return client, registration.json()


def create_workspace(client: TestClient, name: str = "MultiTurn Workspace") -> dict:
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_conversation(client: TestClient, workspace_id: str, title: str | None = None) -> dict:
    payload = {"title": title} if title else {}
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/conversations", json=payload
    )
    assert response.status_code == 201
    return response.json()


def create_evidence_chunk(workspace_id: str, user_id: int, text: str = "Sample chunk text", page: int = 1) -> RetrievedChunk:
    with SessionLocal() as db:
        document = Document(
            workspace_id=UUID(workspace_id),
            uploaded_by=user_id,
            original_filename="neural_networks.pdf",
            storage_provider="test",
            storage_key=f"tests/{uuid.uuid4()}.pdf",
            content_type="application/pdf",
            file_size=200,
            checksum="e" * 64,
            status="PROCESSED",
            page_count=5,
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
            approximate_token_count=15,
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
            similarity=0.92,
        )


# ---------------------------------------------------------------------------
# Unit Tests for Query Rewriter Logic
# ---------------------------------------------------------------------------

def test_extract_core_subject():
    assert extract_core_subject("What is a Convolutional Neural Network?") == "Convolutional Neural Network"
    assert extract_core_subject("Can you explain the Backpropagation algorithm please?") == "Backpropagation algorithm"
    assert extract_core_subject("Tell me about Support Vector Machines in detail") == "Support Vector Machines"
    assert extract_core_subject("Give an overview of Deep Learning") == "Deep Learning"
    assert extract_core_subject("Artificial Intelligence") == "Artificial Intelligence"


def test_pronoun_and_reference_resolution():
    history = (
        ("user", "What is Backpropagation?"),
        ("assistant", "Backpropagation is a supervised learning algorithm for training neural networks."),
    )

    # Plural attribute: "What are its advantages?"
    res1 = rewrite_query_for_retrieval("What are its advantages?", history)
    assert res1.is_follow_up is True
    assert res1.resolution_method == "deterministic_pronoun"
    assert "advantages of Backpropagation" in res1.rewritten_query

    # Singular attribute: "What is its main disadvantage?"
    res2 = rewrite_query_for_retrieval("What is its main disadvantage?", history)
    assert res2.is_follow_up is True
    assert "main disadvantage of Backpropagation" in res2.rewritten_query

    # Verb question: "How does it work?"
    res3 = rewrite_query_for_retrieval("How does it work?", history)
    assert res3.is_follow_up is True
    assert "How does Backpropagation work?" in res3.rewritten_query

    # Short substitution: "Tell me more about it"
    res4 = rewrite_query_for_retrieval("Tell me more about it", history)
    assert res4.is_follow_up is True
    assert "Backpropagation" in res4.rewritten_query


def test_hindi_and_translation_followups():
    history = (
        ("user", "Explain the Perceptron model in neural networks"),
        ("assistant", "The perceptron is an algorithm for supervised learning of binary classifiers."),
    )

    # "Translate that into Hindi"
    res1 = rewrite_query_for_retrieval("Translate that into Hindi", history)
    assert res1.is_follow_up is True
    assert res1.resolution_method == "deterministic_translation"
    assert res1.detected_language == "Hindi"
    assert res1.rewritten_query == "Explain the Perceptron model in neural networks"

    # Hindi script: "हिंदी में समझाइए"
    res2 = rewrite_query_for_retrieval("हिंदी में समझाइए", history)
    assert res2.is_follow_up is True
    assert res2.detected_language == "Hindi"

    # Hinglish: "Hindi me samjhao"
    res3 = rewrite_query_for_retrieval("Hindi me samjhao", history)
    assert res3.is_follow_up is True
    assert res3.detected_language == "Hindi"

    # Translation to French
    res4 = rewrite_query_for_retrieval("Translate to French", history)
    assert res4.is_follow_up is True
    assert res4.detected_language == "French"


def test_numbered_ordinal_reference_resolution():
    history = (
        ("user", "List 3 common activation functions"),
        (
            "assistant",
            "Here are three functions:\n"
            "1. **Sigmoid**: maps values between 0 and 1\n"
            "2. **ReLU**: rectified linear unit that outputs max(0, x)\n"
            "3. **Tanh**: hyperbolic tangent function",
        ),
    )

    # "Summarise the second one"
    res1 = rewrite_query_for_retrieval("Summarise the second one", history)
    assert res1.is_follow_up is True
    assert res1.resolution_method == "deterministic_numbered"
    assert "ReLU" in res1.rewritten_query

    # "Explain option 1"
    res2 = rewrite_query_for_retrieval("Explain option 1", history)
    assert res2.is_follow_up is True
    assert "Sigmoid" in res2.rewritten_query

    # "Tell me about the 3rd one"
    res3 = rewrite_query_for_retrieval("Tell me about the 3rd one", history)
    assert res3.is_follow_up is True
    assert "Tanh" in res3.rewritten_query


def test_simplification_and_page_preservation():
    history = (
        ("user", "What is Gradient Descent Optimization?"),
        ("assistant", "It minimizes cost functions iteratively."),
    )

    # Simplification alone
    res1 = rewrite_query_for_retrieval("Explain it more simply", history)
    assert res1.is_follow_up is True
    assert res1.resolution_method == "deterministic_simplification"
    assert "Gradient Descent Optimization" in res1.rewritten_query

    # Simplification with page constraint
    res2 = rewrite_query_for_retrieval("Explain it more simply on page 3", history)
    assert res2.is_follow_up is True
    assert "Gradient Descent Optimization" in res2.rewritten_query
    assert "page 3" in res2.rewritten_query

    # Multi-page range preservation
    res3 = rewrite_query_for_retrieval("What about pages 2 to 5?", history)
    assert res3.is_follow_up is True
    assert "pages 2 to 5" in res3.rewritten_query


def test_ambiguous_and_empty_history_fallback():
    # Empty history
    res1 = rewrite_query_for_retrieval("What are its advantages?", ())
    assert res1.is_follow_up is False
    assert res1.resolution_method == "no_history"
    assert res1.rewritten_query == "What are its advantages?"

    # Completely standalone query with history
    history = (
        ("user", "What is a Neural Network?"),
        ("assistant", "A computational model inspired by the brain."),
    )
    res2 = rewrite_query_for_retrieval("Who founded Apple Computers?", history)
    assert res2.is_follow_up is False
    assert res2.rewritten_query == "Who founded Apple Computers?"


def test_quota_exhaustion_does_not_raise_or_retry():
    history = (
        ("user", "Tell me about Transformers"),
        ("assistant", "Transformers rely on self-attention mechanisms."),
    )
    # LLM provider that raises quota exhaustion
    failing_llm = MockLLMProvider(raise_exc=LLMQuotaExhaustedError("Quota exhausted 429"))

    # Complex follow-up query that passes through to LLM fallback
    res = rewrite_query_for_retrieval("Compare them with RNNs", history, llm_provider=failing_llm)
    # Must safely fall back without error or loop
    assert res.rewritten_query == "Compare them with RNNs"
    assert len(failing_llm.calls) == 1  # Exactly 1 call, zero retry storms


# ---------------------------------------------------------------------------
# Integration Tests with Service and Database
# ---------------------------------------------------------------------------

def test_rag_prepare_question_uses_search_query_and_sets_language(monkeypatch):
    captured_search_query = None

    def fake_search_workspace(db, workspace, query, top_k, embedding_provider):
        nonlocal captured_search_query
        captured_search_query = query
        return [
            RetrievedChunk(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                filename="doc.pdf",
                page_number=2,
                text="Perceptrons are linear binary classifiers.",
                similarity=0.91,
            )
        ]

    monkeypatch.setattr(rag_service.retrieval_service, "search_workspace", fake_search_workspace)

    history = (
        ("user", "Explain the Perceptron"),
        ("assistant", "A perceptron is a fundamental neural network building block."),
    )

    with SessionLocal() as db:
        # Create a mock workspace object
        from app.models.workspace import Workspace
        ws = Workspace(id=uuid.uuid4(), name="Test WS", created_by=1)

        prep = rag_service.prepare_question(
            db=db,
            workspace=ws,
            query="Translate that into Hindi",
            top_k=5,
            answer_language=None,
            embedding_provider=FakeEmbeddingProvider(),
            conversation_history=history,
        )

        # The user's query is preserved
        assert prep.query == "Translate that into Hindi"
        # The search query resolves to the subject of previous turn
        assert captured_search_query == "Explain the Perceptron"
        assert prep.search_query == "Explain the Perceptron"
        # Effective language was detected as Hindi
        assert prep.answer_language == "Hindi"
        # Prompt contains Hindi instruction
        assert prep.prompt is not None
        assert "Answer language preference: Hindi" in prep.prompt.user_prompt


def test_conversation_turn_multi_turn_retrieval_and_citation_integrity(monkeypatch):
    client, user = authenticated_client("multiturn-citations@example.com")
    workspace = create_workspace(client)
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence_chunk(
        workspace["id"],
        user["id"],
        text="A Convolutional Neural Network consists of input, convolutional, pooling, and fully-connected layers.",
        page=3,
    )

    llm = MockLLMProvider(response_text="The main layers are convolution, pooling, and dense layers.")
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: llm

    retrieval_calls: list[str] = []

    def mock_search(db, ws, query, top_k, emb):
        retrieval_calls.append(query)
        return [evidence]

    monkeypatch.setattr(rag_service.retrieval_service, "search_workspace", mock_search)

    try:
        # Turn 1: Initial Question
        res1 = client.post(
            f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages",
            json={"content": "What is a Convolutional Neural Network?"},
        )
        assert res1.status_code == 200
        assert retrieval_calls[-1] == "What is a Convolutional Neural Network?"

        # Turn 2: Follow-up question with pronoun
        res2 = client.post(
            f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages",
            json={"content": "What are its advantages?"},
        )
        assert res2.status_code == 200
        payload2 = res2.json()

        # Check retrieval received the rewritten standalone query
        assert "advantages of Convolutional Neural Network" in retrieval_calls[-1]

        # Check user message stored in DB is the authentic follow-up
        assert payload2["user_message"]["content"] == "What are its advantages?"

        # Check citations point to authentic page 3 chunk
        assert len(payload2["assistant_message"]["sources"]) == 1
        assert payload2["assistant_message"]["sources"][0]["page_number"] == 3
        assert payload2["assistant_message"]["sources"][0]["chunk_id"] == str(evidence.chunk_id)

    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def test_streaming_and_non_streaming_consistency(monkeypatch):
    client, user = authenticated_client("streaming-consistency@example.com")
    workspace = create_workspace(client)
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence_chunk(
        workspace["id"],
        user["id"],
        text="Support Vector Machines find the optimal hyperplane for classification.",
        page=2,
    )

    llm = MockLLMProvider(response_text="SVM works by maximizing the decision margin.")
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: llm

    retrieval_queries: list[str] = []

    def mock_search(db, ws, query, top_k, emb):
        retrieval_queries.append(query)
        return [evidence]

    monkeypatch.setattr(rag_service.retrieval_service, "search_workspace", mock_search)

    try:
        # Turn 1: Regular message
        client.post(
            f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages",
            json={"content": "Explain Support Vector Machines"},
        )

        # Turn 2: Streaming follow-up
        stream_res = client.post(
            f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages/stream",
            json={"content": "How does it work?"},
        )
        assert stream_res.status_code == 200
        # The retrieval search query for the stream was rewritten
        assert "How does Support Vector Machines work?" in retrieval_queries[-1]

        # Check persisted messages in conversation
        msg_res = client.get(
            f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages"
        )
        assert msg_res.status_code == 200
        messages = msg_res.json()["items"]
        assert len(messages) == 4
        # User message content is intact
        assert messages[2]["content"] == "How does it work?"
        # Assistant message has citations
        assert len(messages[3]["sources"]) == 1
        assert messages[3]["sources"][0]["page_number"] == 2

    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def test_workspace_isolation_in_conversation_history():
    owner1, user1 = authenticated_client("user1-iso@example.com")
    owner2, user2 = authenticated_client("user2-iso@example.com")

    ws1 = create_workspace(owner1, "Workspace 1")
    ws2 = create_workspace(owner2, "Workspace 2")

    conv1 = create_conversation(owner1, ws1["id"], "Secret Project A")
    conv2 = create_conversation(owner2, ws2["id"], "Project B")

    # User 1 sends a turn in conv 1
    with SessionLocal() as db:
        c1 = db.get(Conversation, UUID(conv1["id"]))
        db.add(ConversationMessage(conversation_id=c1.id, role="USER", content="Confidential Financial Data"))
        db.add(ConversationMessage(conversation_id=c1.id, role="ASSISTANT", content="Financial analysis."))
        db.commit()

        # Check bounded_history for conv 2 in workspace 2: must be completely empty!
        c2 = db.get(Conversation, UUID(conv2["id"]))
        h2 = conversation_service.bounded_history(db, c2)
        assert h2 == ()
