import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.session import SessionLocal
from app.embeddings.deps import get_embedding_provider
from app.llm import GenerationResult, LLMProviderError
from app.llm.deps import get_llm_provider
from app.main import app
from app.models.conversation import Conversation, ConversationMessage
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.extracted_page import ExtractedPage
from app.models.rag_citation import RAGCitation
from app.models.rag_response import RAGResponseRecord
from app.models.workspace import WorkspaceMembership
from app.services import conversation as conversation_service
from app.services import rag as rag_service
from app.services.retrieval import RetrievedChunk


class UnusedEmbeddingProvider:
    provider_name = "fake"
    model_name = "fake-embedding"
    dimension = EMBEDDING_DIMENSION

    def embed_documents(self, texts):
        raise AssertionError("not used")

    def embed_query(self, text):
        raise AssertionError("retrieval is replaced in conversation tests")


class CapturingLLMProvider:
    provider_name = "fake"
    model_name = "fake-conversation-model"

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def generate(self, system_instruction, user_prompt):
        self.calls.append((system_instruction, user_prompt))
        return GenerationResult("Persistent grounded answer.", self.model_name, "STOP")


@pytest.fixture
def conversation_providers():
    llm = CapturingLLMProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: UnusedEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: llm
    try:
        yield llm
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def authenticated_client(email: str) -> tuple[TestClient, dict]:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "conversation-test-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "conversation-test-password"},
    )
    assert login.status_code == 200
    return client, registration.json()


def create_workspace(client: TestClient, name: str = "Conversation workspace") -> dict:
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


def add_member(workspace_id: str, user_id: int) -> None:
    with SessionLocal.begin() as db:
        db.add(
            WorkspaceMembership(
                workspace_id=UUID(workspace_id), user_id=user_id, role="MEMBER"
            )
        )


def create_evidence(workspace_id: str, user_id: int) -> RetrievedChunk:
    with SessionLocal() as db:
        document = Document(
            workspace_id=UUID(workspace_id),
            uploaded_by=user_id,
            original_filename="conversation-source.pdf",
            storage_provider="test",
            storage_key=f"tests/{uuid.uuid4()}.pdf",
            content_type="application/pdf",
            file_size=100,
            checksum="d" * 64,
            status="PROCESSED",
            page_count=1,
            indexing_status="INDEXED",
            embedding_model="fake-embedding",
            embedding_dimension=EMBEDDING_DIMENSION,
        )
        db.add(document)
        db.flush()
        page = ExtractedPage(
            document_id=document.id,
            page_number=4,
            text="The authorized source supports this answer.",
            character_count=43,
        )
        db.add(page)
        db.flush()
        chunk = DocumentChunk(
            document_id=document.id,
            extracted_page_id=page.id,
            page_number=4,
            chunk_index=0,
            page_chunk_index=0,
            text=page.text,
            character_count=len(page.text),
            approximate_token_count=11,
            embedding=[0.0] * EMBEDDING_DIMENSION,
            embedding_model="fake-embedding",
        )
        db.add(chunk)
        db.flush()
        result = RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            filename=document.original_filename,
            page_number=4,
            text=chunk.text,
            similarity=0.94,
        )
        db.commit()
        return result


def test_create_list_get_rename_and_order_conversations():
    client, _ = authenticated_client("conversation-crud@example.com")
    workspace = create_workspace(client)
    first = create_conversation(client, workspace["id"], "First research")
    second = create_conversation(client, workspace["id"], "Second research")

    listing = client.get(f"/api/v1/workspaces/{workspace['id']}/conversations")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]][:2] == [second["id"], first["id"]]
    detail = client.get(
        f"/api/v1/workspaces/{workspace['id']}/conversations/{first['id']}"
    )
    assert detail.status_code == 200
    renamed = client.patch(
        f"/api/v1/workspaces/{workspace['id']}/conversations/{first['id']}",
        json={"title": "Renamed evidence review"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed evidence review"


def test_conversation_is_private_to_creator_even_for_workspace_member():
    owner, _ = authenticated_client("conversation-owner@example.com")
    member, member_user = authenticated_client("conversation-member@example.com")
    workspace = create_workspace(owner)
    add_member(workspace["id"], member_user["id"])
    conversation = create_conversation(owner, workspace["id"], "Owner notes")

    assert member.get(f"/api/v1/workspaces/{workspace['id']}/conversations").json()["items"] == []
    hidden = member.get(
        f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}"
    )
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "Conversation not found"


def test_nonmember_cross_workspace_and_unauthenticated_access_are_rejected():
    owner, _ = authenticated_client("conversation-security-owner@example.com")
    outsider, _ = authenticated_client("conversation-security-outsider@example.com")
    workspace = create_workspace(owner)
    conversation = create_conversation(owner, workspace["id"])
    path = f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}"

    assert TestClient(app).get(path).status_code == 401
    concealed = outsider.get(path)
    assert concealed.status_code == 404
    assert concealed.json()["detail"] == "Workspace not found"
    other_workspace = create_workspace(owner, "Other boundary")
    crossed = owner.get(
        f"/api/v1/workspaces/{other_workspace['id']}/conversations/{conversation['id']}"
    )
    assert crossed.status_code == 404


def test_turn_persists_user_assistant_response_and_authoritative_citation(
    monkeypatch, conversation_providers
):
    client, user = authenticated_client("conversation-turn@example.com")
    workspace = create_workspace(client)
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence(workspace["id"], user["id"])
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: [evidence]
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages",
        json={"content": "What does the authorized source establish?", "answer_language": "English"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["title"] == "What does the authorized source establish?"
    assert payload["user_message"]["role"] == "USER"
    assert payload["assistant_message"]["role"] == "ASSISTANT"
    assert payload["assistant_message"]["sources"][0]["chunk_id"] == str(evidence.chunk_id)

    messages = client.get(
        f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages"
    )
    assert messages.status_code == 200
    assert [item["role"] for item in messages.json()["items"]] == ["USER", "ASSISTANT"]
    assert messages.json()["items"][1]["sources"][0]["page_number"] == 4
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count())
            .select_from(ConversationMessage)
            .where(ConversationMessage.conversation_id == UUID(conversation["id"]))
        ) == 2
        assistant_record = db.get(
            ConversationMessage, UUID(payload["assistant_message"]["id"])
        )
        assert assistant_record is not None
        assert assistant_record.rag_response_id is not None
        rag_response_id = assistant_record.rag_response_id
        assert db.scalar(
            select(func.count())
            .select_from(RAGResponseRecord)
            .where(RAGResponseRecord.id == rag_response_id)
        ) == 1
        assert db.scalar(
            select(func.count())
            .select_from(RAGCitation)
            .where(RAGCitation.response_id == rag_response_id)
        ) == 1


def test_follow_up_uses_bounded_recent_context_and_fresh_retrieval(
    monkeypatch, conversation_providers
):
    client, user = authenticated_client("conversation-context@example.com")
    workspace = create_workspace(client)
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence(workspace["id"], user["id"])
    retrieval_queries: list[str] = []

    def retrieve(db, authorized_workspace, query, top_k, provider):
        retrieval_queries.append(query)
        return [evidence]

    monkeypatch.setattr(rag_service.retrieval_service, "search_workspace", retrieve)
    path = f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages"
    assert client.post(path, json={"content": "Establish the first finding."}).status_code == 200
    assert client.post(path, json={"content": "How does that affect the conclusion?"}).status_code == 200

    assert retrieval_queries == ["Establish the first finding.", "How does that affect the conclusion?"]
    second_prompt = conversation_providers.calls[1][1]
    assert "RECENT CONVERSATION CONTEXT (NOT EVIDENCE)" in second_prompt
    assert "Establish the first finding." in second_prompt
    assert "Persistent grounded answer." in second_prompt
    assert second_prompt.index("RECENT CONVERSATION") < second_prompt.index("RETRIEVED EVIDENCE")


def test_bounded_history_enforces_message_and_character_limits(monkeypatch):
    client, _ = authenticated_client("conversation-bounds@example.com")
    workspace = create_workspace(client)
    created = create_conversation(client, workspace["id"])
    conversation_id = UUID(created["id"])
    with SessionLocal() as db:
        base_time = datetime.now(timezone.utc)
        for index in range(12):
            db.add(
                ConversationMessage(
                    conversation_id=conversation_id,
                    role="USER" if index % 2 == 0 else "ASSISTANT",
                    content=f"message-{index}-" + "x" * 30,
                    created_at=base_time + timedelta(seconds=index),
                )
            )
        db.commit()
    monkeypatch.setattr(settings, "CONVERSATION_HISTORY_MAX_MESSAGES", 4)
    monkeypatch.setattr(settings, "CONVERSATION_HISTORY_MAX_CHARACTERS", 70)
    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        history = conversation_service.bounded_history(db, conversation)
    assert len(history) <= 4
    assert sum(len(content) for _, content in history) <= 70
    assert "message-11" in history[-1][1]
    assert all("message-0" not in content for _, content in history)


def test_insufficient_evidence_persists_assistant_message_without_llm(
    monkeypatch, conversation_providers
):
    client, _ = authenticated_client("conversation-insufficient@example.com")
    workspace = create_workspace(client)
    conversation = create_conversation(client, workspace["id"])
    monkeypatch.setattr(rag_service.retrieval_service, "search_workspace", lambda *args: [])
    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages",
        json={"content": "What is not in the sources?"},
    )
    assert response.status_code == 200
    assistant = response.json()["assistant_message"]
    assert assistant["insufficient_evidence"] is True
    assert assistant["sources"] == []
    assert conversation_providers.calls == []
    with SessionLocal() as db:
        record = db.get(RAGResponseRecord, UUID(assistant["response_id"]))
        assert record.insufficient_evidence is True
        assert record.citation_count == 0


def test_provider_failure_rolls_back_the_incomplete_turn(
    monkeypatch, conversation_providers
):
    class FailingLLM(CapturingLLMProvider):
        def generate(self, system_instruction, user_prompt):
            raise LLMProviderError("private provider diagnostic")

    app.dependency_overrides[get_llm_provider] = lambda: FailingLLM()
    client, user = authenticated_client("conversation-provider-error@example.com")
    workspace = create_workspace(client)
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence(workspace["id"], user["id"])
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: [evidence]
    )
    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages",
        json={"content": "A question that fails safely"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "LLM_PROVIDER_ERROR",
        "message": "Grounded answer generation failed",
    }
    messages = client.get(
        f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}/messages"
    ).json()["items"]
    assert messages == []
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(RAGResponseRecord).where(
                RAGResponseRecord.workspace_id == UUID(workspace["id"])
            )
        ) == 0


def test_delete_conversation_cascades_messages_linked_response_and_citations(
    monkeypatch, conversation_providers
):
    client, user = authenticated_client("conversation-delete@example.com")
    workspace = create_workspace(client)
    conversation = create_conversation(client, workspace["id"])
    evidence = create_evidence(workspace["id"], user["id"])
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: [evidence]
    )
    path = f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}"
    assert client.post(f"{path}/messages", json={"content": "Persist then delete"}).status_code == 200
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    with SessionLocal() as db:
        assert db.get(Conversation, UUID(conversation["id"])) is None
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
        assert db.scalar(
            select(func.count()).select_from(RAGCitation).join(RAGResponseRecord).where(
                RAGResponseRecord.workspace_id == UUID(workspace["id"])
            )
        ) == 0
        assert db.get(Document, evidence.document_id) is not None


def test_conversation_migration_upgrade_downgrade_and_reupgrade(
    disposable_database, run_alembic
):
    database_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    engine = create_engine(database_url)
    try:
        run_alembic("upgrade", "b84cf6e207d9", database=disposable_database)
        run_alembic("upgrade", "head", database=disposable_database)
        with engine.connect() as connection:
            tables = set(connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).scalars())
            assert {"conversations", "conversation_messages"}.issubset(tables)
        run_alembic("downgrade", "b84cf6e207d9", database=disposable_database)
        with engine.connect() as connection:
            tables = set(connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).scalars())
            assert not {"conversations", "conversation_messages"} & tables
        run_alembic("upgrade", "head", database=disposable_database)
    finally:
        engine.dispose()
