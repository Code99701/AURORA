import asyncio
import json
import uuid
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.embeddings.deps import get_embedding_provider
from app.llm import (
    GenerationResult,
    LLMProviderError,
    LLMRateLimitError,
    StreamingGenerationEvent,
)
from app.llm.deps import get_llm_provider
from app.llm.ollama import OllamaLLMProvider
from app.main import app
from app.models.conversation import Conversation, ConversationMessage
from app.models.rag_citation import RAGCitation
from app.models.rag_response import RAGResponseRecord
from app.services import conversation as conversation_service
from app.services import rag as rag_service
from app.services import retrieval as retrieval_service
from tests.test_conversations import (
    UnusedEmbeddingProvider,
    add_member,
    authenticated_client,
    create_conversation,
    create_evidence,
    create_workspace,
)


class StreamingLLMProvider:
    provider_name = "fake"
    model_name = "fake-stream-model"

    def __init__(self, events=None, error=None, include_completion=True):
        self.events = events or ["Grounded ", "streamed answer."]
        self.error = error
        self.include_completion = include_completion
        self.stream_calls = []
        self.sync_calls = []
        self.closed = False

    def generate(self, system_instruction, user_prompt):
        self.sync_calls.append((system_instruction, user_prompt))
        return GenerationResult("Synchronous fallback answer.", self.model_name, "STOP")

    async def stream_generate(self, system_instruction, user_prompt):
        self.stream_calls.append((system_instruction, user_prompt))
        try:
            for text in self.events:
                yield StreamingGenerationEvent(event_type="text_delta", text=text)
                await asyncio.sleep(0)
            if self.error:
                raise self.error
            if self.include_completion:
                yield StreamingGenerationEvent(
                    event_type="completion",
                    model_name=self.model_name,
                    finish_reason="STOP",
                    usage={"totalTokenCount": 12},
                )
        finally:
            self.closed = True


def parse_sse(response) -> list[tuple[str, dict]]:
    events = []
    event_name = None
    data_lines = []
    for line in response.text.splitlines() + [""]:
        if line.startswith("event: "):
            event_name = line[7:]
        elif line.startswith("data: "):
            data_lines.append(line[6:])
        elif not line and event_name:
            events.append((event_name, json.loads("\n".join(data_lines))))
            event_name = None
            data_lines = []
    return events


@pytest.fixture
def streaming_provider():
    provider = StreamingLLMProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: UnusedEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    try:
        yield provider
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def stream_path(workspace_id: str, conversation_id: str) -> str:
    return (
        f"/api/v1/workspaces/{workspace_id}/conversations/"
        f"{conversation_id}/messages/stream"
    )


def test_authenticated_stream_emits_deltas_completes_and_persists_citations(
    monkeypatch, streaming_provider
):
    client, user = authenticated_client("stream-success@example.com")
    workspace = create_workspace(client, "Streaming success")
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence(workspace["id"], user["id"])
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: [evidence]
    )

    response = client.post(
        stream_path(workspace["id"], conversation["id"]),
        json={"content": "What is established?", "answer_language": "English"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response)
    assert [name for name, _ in events] == [
        "state",
        "state",
        "text_delta",
        "text_delta",
        "state",
        "complete",
    ], events
    assert [payload["phase"] for name, payload in events if name == "state"] == [
        "retrieving",
        "streaming",
        "finalizing",
    ]
    assert "".join(payload["text"] for name, payload in events if name == "text_delta") == (
        "Grounded streamed answer."
    )
    completed = events[-1][1]
    assert completed["assistant_message"]["content"] == "Grounded streamed answer."
    assert completed["assistant_message"]["sources"][0]["chunk_id"] == str(
        evidence.chunk_id
    )
    with SessionLocal() as db:
        messages = list(
            db.scalars(
                select(ConversationMessage).where(
                    ConversationMessage.conversation_id == UUID(conversation["id"])
                )
            ).all()
        )
        assert [message.role for message in messages] == ["USER", "ASSISTANT"]
        response_id = messages[1].rag_response_id
        assert response_id is not None
        assert db.get(RAGResponseRecord, response_id).answer == "Grounded streamed answer."
        assert db.scalar(
            select(func.count()).select_from(RAGCitation).where(
                RAGCitation.response_id == response_id
            )
        ) == 1


def test_stream_authorization_rejects_unauthenticated_nonmember_cross_user_and_cross_workspace(
    streaming_provider
):
    owner, _ = authenticated_client("stream-owner@example.com")
    member, member_user = authenticated_client("stream-member@example.com")
    outsider, _ = authenticated_client("stream-outsider@example.com")
    workspace = create_workspace(owner, "Streaming private")
    other = create_workspace(owner, "Streaming other")
    add_member(workspace["id"], member_user["id"])
    conversation = create_conversation(owner, workspace["id"])
    path = stream_path(workspace["id"], conversation["id"])
    payload = {"content": "Secret question"}

    assert TestClient(app).post(path, json=payload).status_code == 401
    assert outsider.post(path, json=payload).status_code == 404
    assert member.post(path, json=payload).status_code == 404
    assert owner.post(
        stream_path(other["id"], conversation["id"]), json=payload
    ).status_code == 404
    assert streaming_provider.stream_calls == []


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (LLMProviderError("private provider payload"), "LLM_PROVIDER_ERROR"),
        (LLMRateLimitError("private quota payload"), "LLM_RATE_LIMIT_ERROR"),
    ],
)
def test_stream_provider_failures_are_terminal_sanitized_and_not_persisted(
    monkeypatch, error, expected_code
):
    provider = StreamingLLMProvider(events=["Partial unsafe answer"], error=error)
    app.dependency_overrides[get_embedding_provider] = lambda: UnusedEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    try:
        client, user = authenticated_client(f"stream-failure-{uuid.uuid4()}@example.com")
        workspace = create_workspace(client, "Streaming failure")
        conversation = create_conversation(client, workspace["id"])
        evidence = create_evidence(workspace["id"], user["id"])
        monkeypatch.setattr(
            rag_service.retrieval_service,
            "search_workspace",
            lambda *args: [evidence],
        )
        response = client.post(
            stream_path(workspace["id"], conversation["id"]),
            json={"content": "Fail safely"},
        )
        events = parse_sse(response)
        assert events[-1] == (
            "error",
            {
                "code": expected_code,
                "message": (
                    "Generation service is temporarily rate limited"
                    if expected_code == "LLM_RATE_LIMIT_ERROR"
                    else "Grounded answer generation failed"
                ),
                "retryable": True,
            },
        )
        assert "private" not in response.text
        assert all(name != "complete" for name, _ in events)
        with SessionLocal() as db:
            assert db.scalar(
                select(func.count()).select_from(ConversationMessage).where(
                    ConversationMessage.conversation_id == UUID(conversation["id"])
                )
            ) == 0
            assert db.scalar(
                select(func.count()).select_from(RAGResponseRecord).where(
                    RAGResponseRecord.workspace_id == UUID(workspace["id"])
                )
            ) == 0
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def test_no_ready_sources_stream_returns_stable_conflict_without_provider_call(
    streaming_provider,
):
    client, _ = authenticated_client("stream-insufficient@example.com")
    workspace = create_workspace(client, "Streaming insufficient")
    conversation = create_conversation(client, workspace["id"])
    response = client.post(
        stream_path(workspace["id"], conversation["id"]),
        json={"content": "What is absent?"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "NO_RESEARCH_READY_SOURCES"
    assert streaming_provider.stream_calls == []


def test_insufficient_evidence_stream_is_deterministic_without_provider_call(
    monkeypatch, streaming_provider
):
    client, user = authenticated_client("stream-indexed-insufficient@example.com")
    workspace = create_workspace(client, "Streaming insufficient")
    conversation = create_conversation(client, workspace["id"])
    create_evidence(workspace["id"], user["id"])
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: []
    )

    response = client.post(
        stream_path(workspace["id"], conversation["id"]),
        json={"content": "What is absent?"},
    )
    assert response.status_code == 200
    events = parse_sse(response)
    assert events[-1][0] == "complete"
    assistant = events[-1][1]["assistant_message"]
    assert assistant["insufficient_evidence"] is True
    assert assistant["sources"] == []
    assert streaming_provider.stream_calls == []


def test_persistence_failure_after_generation_sends_error_without_completion(
    monkeypatch, streaming_provider
):
    client, user = authenticated_client("stream-persistence-error@example.com")
    workspace = create_workspace(client, "Streaming persistence failure")
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence(workspace["id"], user["id"])
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: [evidence]
    )

    def fail_persistence(*args, **kwargs):
        raise rag_service.RAGError(
            "RAG_PERSISTENCE_ERROR",
            "Generated response and citations could not be saved",
            500,
        )

    monkeypatch.setattr(rag_service, "persist_prepared_answer", fail_persistence)
    response = client.post(
        stream_path(workspace["id"], conversation["id"]),
        json={"content": "Generate then fail persistence"},
    )
    events = parse_sse(response)
    assert any(name == "text_delta" for name, _ in events)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "RAG_PERSISTENCE_ERROR"
    assert all(name != "complete" for name, _ in events)
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(ConversationMessage).where(
                ConversationMessage.conversation_id == UUID(conversation["id"])
            )
        ) == 0


def test_stream_retrieval_and_malformed_provider_failures_are_terminal(monkeypatch):
    client, user = authenticated_client("stream-terminal-errors@example.com")
    workspace = create_workspace(client, "Streaming terminal errors")
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence(workspace["id"], user["id"])
    app.dependency_overrides[get_embedding_provider] = lambda: UnusedEmbeddingProvider()
    try:
        provider = StreamingLLMProvider(
            events=["Incomplete"], include_completion=False
        )
        app.dependency_overrides[get_llm_provider] = lambda: provider
        monkeypatch.setattr(
            rag_service.retrieval_service,
            "search_workspace",
            lambda *args: [evidence],
        )
        malformed = client.post(
            stream_path(workspace["id"], conversation["id"]),
            json={"content": "Malformed provider stream"},
        )
        malformed_events = parse_sse(malformed)
        assert malformed_events[-1][0] == "error"
        assert malformed_events[-1][1]["code"] == "LLM_PROVIDER_ERROR"
        assert all(name != "complete" for name, _ in malformed_events)

        def fail_retrieval(*args):
            raise retrieval_service.RetrievalError(
                "RETRIEVAL_FAILED", "private retrieval detail", 503
            )

        monkeypatch.setattr(
            rag_service.retrieval_service, "search_workspace", fail_retrieval
        )
        retrieval = client.post(
            stream_path(workspace["id"], conversation["id"]),
            json={"content": "Retrieval fails"},
        )
        retrieval_events = parse_sse(retrieval)
        assert retrieval_events[-1] == (
            "error",
            {
                "code": "RAG_RETRIEVAL_ERROR",
                "message": "Authorized evidence retrieval failed",
                "retryable": True,
            },
        )
        assert "private retrieval detail" not in retrieval.text
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def test_provider_secret_never_appears_in_stream_error(monkeypatch):
    secret = "configured-provider-secret"
    provider = StreamingLLMProvider(
        events=["Partial"], error=LLMProviderError(f"credential={secret}")
    )
    app.dependency_overrides[get_embedding_provider] = lambda: UnusedEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    try:
        client, user = authenticated_client("stream-secret@example.com")
        workspace = create_workspace(client, "Streaming secret safety")
        conversation = create_conversation(client, workspace["id"])
        evidence = create_evidence(workspace["id"], user["id"])
        monkeypatch.setattr(
            rag_service.retrieval_service,
            "search_workspace",
            lambda *args: [evidence],
        )
        response = client.post(
            stream_path(workspace["id"], conversation["id"]),
            json={"content": "Do not expose secrets"},
        )
        assert secret not in response.text
        assert parse_sse(response)[-1][1]["message"] == (
            "Grounded answer generation failed"
        )
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def test_client_cancellation_closes_provider_and_rolls_back_staged_turn(
    monkeypatch, streaming_provider
):
    client, user = authenticated_client("stream-cancel@example.com")
    workspace_data = create_workspace(client, "Streaming cancellation")
    conversation_data = create_conversation(client, workspace_data["id"])
    evidence = create_evidence(workspace_data["id"], user["id"])
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: [evidence]
    )

    async def cancel_after_first_delta():
        with SessionLocal() as db:
            conversation = db.get(Conversation, UUID(conversation_data["id"]))
            workspace = conversation.workspace
            stream = conversation_service.stream_message(
                db,
                workspace,
                conversation.user,
                conversation,
                "Cancel this generation",
                5,
                None,
                UnusedEmbeddingProvider(),
                streaming_provider,
            )
            while True:
                event = await anext(stream)
                if event.event_type == "text_delta":
                    break
            await stream.aclose()

    asyncio.run(cancel_after_first_delta())
    assert streaming_provider.closed is True
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(ConversationMessage).where(
                ConversationMessage.conversation_id == UUID(conversation_data["id"])
            )
        ) == 0


def test_stream_request_rejects_client_controlled_evidence_identity(streaming_provider):
    client, _ = authenticated_client("stream-schema@example.com")
    workspace = create_workspace(client, "Streaming schema")
    conversation = create_conversation(client, workspace["id"])
    response = client.post(
        stream_path(workspace["id"], conversation["id"]),
        json={
            "content": "Do not trust these IDs",
            "citation_ids": [str(uuid.uuid4())],
            "document_ids": [str(uuid.uuid4())],
            "chunk_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 422
    assert streaming_provider.stream_calls == []


def test_existing_synchronous_conversation_endpoint_remains_functional(
    monkeypatch, streaming_provider
):
    client, user = authenticated_client("stream-sync-regression@example.com")
    workspace = create_workspace(client, "Synchronous fallback")
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence(workspace["id"], user["id"])
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: [evidence]
    )
    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/conversations/"
        f"{conversation['id']}/messages",
        json={"content": "Use the synchronous fallback"},
    )
    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"] == (
        "Synchronous fallback answer."
    )
    assert len(streaming_provider.sync_calls) == 1
    assert streaming_provider.stream_calls == []


def test_ollama_adapter_normalizes_stream_ndjson(monkeypatch):
    lines = [
        json.dumps({"message": {"content": "Ollama "}, "done": False}),
        json.dumps({"message": {"content": "stream"}, "done": True, "done_reason": "stop"}),
    ]

    class FakeResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for line in lines:
                yield line

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OllamaLLMProvider(base_url="http://127.0.0.1:11434", model_name="qwen3:8b", think=False)

    async def collect():
        return [
            event
            async for event in provider.stream_generate("system", "question")
        ]

    events = asyncio.run(collect())
    assert [event.event_type for event in events] == [
        "text_delta",
        "text_delta",
        "completion",
    ]
    assert "".join(event.text for event in events) == "Ollama stream"
    assert events[-1].model_name == "ollama/qwen3:8b"
    assert events[-1].finish_reason == "stop"


def test_ollama_adapter_handles_missing_model_stream(monkeypatch):
    class FakeResponse:
        status_code = 404

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def raise_for_status(self):
            req = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
            raise httpx.HTTPStatusError("Not found", request=req, response=httpx.Response(404, request=req))

        async def aiter_lines(self):
            yield '{"error": "model not found"}'

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OllamaLLMProvider(base_url="http://127.0.0.1:11434", model_name="qwen3:8b", think=False)

    async def collect():
        return [
            event
            async for event in provider.stream_generate("system", "question")
        ]

    with pytest.raises(LLMProviderError, match="model 'qwen3:8b' was not found"):
        asyncio.run(collect())

