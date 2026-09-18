import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import SessionLocal
from app.embeddings.deps import get_embedding_provider
from app.llm import GenerationResult, LLMProviderError
from app.llm.deps import get_llm_provider
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.extracted_page import ExtractedPage
from app.models.rag_citation import RAGCitation
from app.models.rag_response import RAGResponseRecord
from app.models.workspace import Workspace
from app.services import rag as rag_service
from app.services.retrieval import RetrievedChunk


class UnusedEmbeddingProvider:
    provider_name = "fake"
    model_name = "fake-embedding"
    dimension = EMBEDDING_DIMENSION

    def embed_documents(self, texts):
        raise AssertionError("not used")

    def embed_query(self, text):
        raise AssertionError("retrieval is replaced by authorized test evidence")


class DeterministicLLMProvider:
    provider_name = "fake"
    model_name = "fake-citation-model"

    def generate(self, system_instruction, user_prompt):
        return GenerationResult("Persisted grounded answer.", self.model_name, "STOP")


@pytest.fixture
def citation_providers():
    app.dependency_overrides[get_embedding_provider] = lambda: UnusedEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: DeterministicLLMProvider()
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def authenticated_client(email: str) -> tuple[TestClient, dict]:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "citation-foundation-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "citation-foundation-password"},
    )
    assert login.status_code == 200
    return client, registration.json()


def create_workspace(client: TestClient, name: str) -> dict:
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_indexed_document(
    workspace_id: str,
    user_id: int,
    filename: str,
    page_texts: list[tuple[int, str]],
) -> tuple[UUID, list[RetrievedChunk]]:
    with SessionLocal() as db:
        document = Document(
            workspace_id=UUID(workspace_id),
            uploaded_by=user_id,
            original_filename=filename,
            storage_provider="test",
            storage_key=f"tests/{uuid.uuid4()}.pdf",
            content_type="application/pdf",
            file_size=100,
            checksum="c" * 64,
            status="PROCESSED",
            page_count=len(page_texts),
            indexing_status="INDEXED",
            embedding_model="fake-embedding",
            embedding_dimension=EMBEDDING_DIMENSION,
        )
        db.add(document)
        db.flush()
        results = []
        for index, (page_number, content) in enumerate(page_texts):
            page = ExtractedPage(
                document_id=document.id,
                page_number=page_number,
                text=content,
                character_count=len(content),
            )
            db.add(page)
            db.flush()
            vector = [0.0] * EMBEDDING_DIMENSION
            vector[index % 10] = 1.0
            chunk = DocumentChunk(
                document_id=document.id,
                extracted_page_id=page.id,
                page_number=page_number,
                chunk_index=index,
                page_chunk_index=0,
                text=content,
                character_count=len(content),
                approximate_token_count=max(1, (len(content) + 3) // 4),
                embedding=vector,
                embedding_model="fake-embedding",
            )
            db.add(chunk)
            db.flush()
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    filename=filename,
                    page_number=page_number,
                    text=content,
                    similarity=0.95 - index * 0.05,
                )
            )
        document_id = document.id
        db.commit()
        return document_id, results


def test_successful_response_and_multi_document_citations_persist_with_provenance(
    monkeypatch, citation_providers
):
    client, user = authenticated_client("citations-persist@example.com")
    workspace = create_workspace(client, "Persistent citations")
    first_document, first_chunks = create_indexed_document(
        workspace["id"], user["id"], "research-a.pdf", [(3, "Evidence A3"), (5, "Evidence A5")]
    )
    second_document, second_chunks = create_indexed_document(
        workspace["id"], user["id"], "research-b.pdf", [(7, "Evidence B7")]
    )
    ordered = [first_chunks[0], second_chunks[0], first_chunks[1], first_chunks[0]]
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: ordered
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/rag",
        json={"query": "Combine the authorized evidence", "top_k": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    response_id = UUID(payload["response_id"])
    assert payload["answer"] == "Persisted grounded answer."
    assert [source["position"] for source in payload["sources"]] == [1, 2, 3]
    assert [source["chunk_id"] for source in payload["sources"]] == [
        str(first_chunks[0].chunk_id),
        str(second_chunks[0].chunk_id),
        str(first_chunks[1].chunk_id),
    ]
    assert [source["document_id"] for source in payload["sources"]] == [
        str(first_document),
        str(second_document),
        str(first_document),
    ]
    assert len({source["citation_id"] for source in payload["sources"]}) == 3

    with SessionLocal() as db:
        record = db.get(RAGResponseRecord, response_id)
        assert record.workspace_id == UUID(workspace["id"])
        assert record.requested_by == user["id"]
        assert record.query == "Combine the authorized evidence"
        assert record.citation_count == 3
        citations = db.scalars(
            select(RAGCitation)
            .where(RAGCitation.response_id == response_id)
            .order_by(RAGCitation.position)
        ).all()
        assert [citation.chunk_id for citation in citations] == [
            first_chunks[0].chunk_id,
            second_chunks[0].chunk_id,
            first_chunks[1].chunk_id,
        ]
        assert citations[0].chunk.extracted_page.page_number == 3
        assert citations[1].chunk.document.original_filename == "research-b.pdf"
        assert citations[1].chunk.document.workspace_id == UUID(workspace["id"])

    fetched = client.get(
        f"/api/v1/workspaces/{workspace['id']}/rag/responses/{response_id}"
    )
    assert fetched.status_code == 200
    assert fetched.json() == payload

    resolved = client.get(
        f"/api/v1/workspaces/{workspace['id']}/rag/citations/"
        f"{payload['sources'][1]['citation_id']}"
    )
    assert resolved.status_code == 200
    assert resolved.json() == payload["sources"][1]


def test_insufficient_evidence_response_is_persisted_without_citations(
    monkeypatch, citation_providers
):
    client, _ = authenticated_client("citations-insufficient@example.com")
    workspace = create_workspace(client, "Insufficient evidence history")
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: []
    )
    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/rag", json={"query": "Unknown"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["insufficient_evidence"] is True
    assert payload["sources"] == []
    with SessionLocal() as db:
        record = db.get(RAGResponseRecord, UUID(payload["response_id"]))
        assert record is not None
        assert record.citation_count == 0
        assert record.model is None


def test_response_lookup_is_concealed_across_users_workspaces_and_invalid_ids(
    monkeypatch, citation_providers
):
    owner, user = authenticated_client("citations-owner@example.com")
    outsider, _ = authenticated_client("citations-outsider@example.com")
    first = create_workspace(owner, "Citation owner workspace")
    second = create_workspace(owner, "Citation second workspace")
    _, chunks = create_indexed_document(
        first["id"], user["id"], "private.pdf", [(1, "Private evidence")]
    )
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: chunks
    )
    created = owner.post(
        f"/api/v1/workspaces/{first['id']}/rag", json={"query": "Private?"}
    ).json()
    response_id = created["response_id"]
    citation_id = created["sources"][0]["citation_id"]

    assert outsider.get(
        f"/api/v1/workspaces/{first['id']}/rag/responses/{response_id}"
    ).status_code == 404
    assert owner.get(
        f"/api/v1/workspaces/{second['id']}/rag/responses/{response_id}"
    ).status_code == 404
    assert owner.get(
        f"/api/v1/workspaces/{first['id']}/rag/responses/{uuid.uuid4()}"
    ).status_code == 404
    # A real citation UUID does not grant access when supplied as a response UUID.
    assert owner.get(
        f"/api/v1/workspaces/{first['id']}/rag/responses/{citation_id}"
    ).status_code == 404
    assert outsider.get(
        f"/api/v1/workspaces/{first['id']}/rag/citations/{citation_id}"
    ).status_code == 404
    assert owner.get(
        f"/api/v1/workspaces/{second['id']}/rag/citations/{citation_id}"
    ).status_code == 404


@pytest.mark.parametrize("field", ["citation_id", "citation_ids", "document_ids", "chunk_ids"])
def test_client_cannot_inject_provenance_identifiers(citation_providers, field):
    client, _ = authenticated_client(f"citations-inject-{field}@example.com")
    workspace = create_workspace(client, f"Reject {field}")
    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/rag",
        json={"query": "Question", field: [str(uuid.uuid4())]},
    )
    assert response.status_code == 422


def test_document_deletion_removes_citations_and_conceals_incomplete_response(
    monkeypatch, citation_providers
):
    client, user = authenticated_client("citations-document-delete@example.com")
    workspace = create_workspace(client, "Citation document deletion")
    first_document, first_chunks = create_indexed_document(
        workspace["id"], user["id"], "delete-me.pdf", [(1, "Delete evidence")]
    )
    _, second_chunks = create_indexed_document(
        workspace["id"], user["id"], "keep-me.pdf", [(2, "Keep evidence")]
    )
    monkeypatch.setattr(
        rag_service.retrieval_service,
        "search_workspace",
        lambda *args: [first_chunks[0], second_chunks[0]],
    )
    created = client.post(
        f"/api/v1/workspaces/{workspace['id']}/rag", json={"query": "Both?"}
    ).json()
    response_id = UUID(created["response_id"])
    deleted_citation_id = created["sources"][0]["citation_id"]

    with SessionLocal() as db:
        db.delete(db.get(Document, first_document))
        db.commit()
        assert db.scalar(
            select(func.count()).select_from(RAGCitation).where(
                RAGCitation.response_id == response_id
            )
        ) == 1
    response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/rag/responses/{response_id}"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "RAG response not found"
    citation = client.get(
        f"/api/v1/workspaces/{workspace['id']}/rag/citations/{deleted_citation_id}"
    )
    assert citation.status_code == 404
    assert citation.json()["detail"] == "Citation source not found"


def test_workspace_deletion_cascades_responses_and_citations(
    monkeypatch, citation_providers
):
    client, user = authenticated_client("citations-workspace-delete@example.com")
    workspace = create_workspace(client, "Delete citation workspace")
    _, chunks = create_indexed_document(
        workspace["id"], user["id"], "workspace.pdf", [(1, "Evidence")]
    )
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: chunks
    )
    created = client.post(
        f"/api/v1/workspaces/{workspace['id']}/rag", json={"query": "Evidence?"}
    ).json()
    response_id = UUID(created["response_id"])
    citation_ids = [UUID(item["citation_id"]) for item in created["sources"]]

    with SessionLocal() as db:
        db.delete(db.get(Workspace, UUID(workspace["id"])))
        db.commit()
        assert db.get(RAGResponseRecord, response_id) is None
        assert all(db.get(RAGCitation, citation_id) is None for citation_id in citation_ids)


def test_citation_persistence_failure_rolls_back_response_and_citations(
    monkeypatch, citation_providers
):
    client, user = authenticated_client("citations-rollback@example.com")
    workspace_payload = create_workspace(client, "Citation rollback")
    _, chunks = create_indexed_document(
        workspace_payload["id"], user["id"], "rollback.pdf", [(1, "Evidence")]
    )
    with SessionLocal() as db:
        workspace = db.get(Workspace, UUID(workspace_payload["id"]))
        monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("fail")))
        with pytest.raises(rag_service.RAGError) as raised:
            rag_service._persist_response(
                db=db,
                workspace=workspace,
                requested_by=user["id"],
                query="Rollback?",
                answer="Generated but not returned",
                answer_language=None,
                top_k=5,
                insufficient_evidence=False,
                model="fake",
                evidence=chunks,
            )
        assert raised.value.code == "RAG_PERSISTENCE_ERROR"

    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(RAGResponseRecord).where(
                RAGResponseRecord.workspace_id == UUID(workspace_payload["id"])
            )
        ) == 0
        assert db.scalar(
            select(func.count()).select_from(RAGCitation).where(
                RAGCitation.chunk_id == chunks[0].chunk_id
            )
        ) == 0


def test_persistence_rejects_cross_workspace_evidence(citation_providers):
    client, user = authenticated_client("citations-boundary@example.com")
    authorized = create_workspace(client, "Authorized citation workspace")
    other = create_workspace(client, "Other citation workspace")
    _, other_chunks = create_indexed_document(
        other["id"], user["id"], "other-private.pdf", [(1, "Other private evidence")]
    )
    with SessionLocal() as db:
        workspace = db.get(Workspace, UUID(authorized["id"]))
        with pytest.raises(rag_service.RAGError) as raised:
            rag_service._persist_response(
                db=db,
                workspace=workspace,
                requested_by=user["id"],
                query="Try cross workspace",
                answer="Must not persist",
                answer_language=None,
                top_k=5,
                insufficient_evidence=False,
                model="fake",
                evidence=other_chunks,
            )
        assert raised.value.code == "RAG_PERSISTENCE_ERROR"
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(RAGResponseRecord).where(
                RAGResponseRecord.workspace_id == UUID(authorized["id"])
            )
        ) == 0


def test_provider_failure_persists_nothing(monkeypatch, citation_providers):
    class FailingProvider:
        provider_name = "fake"
        model_name = "fake"

        def generate(self, system_instruction, user_prompt):
            raise LLMProviderError("private detail")

    client, user = authenticated_client("citations-provider-failure@example.com")
    workspace_payload = create_workspace(client, "No response on provider failure")
    _, chunks = create_indexed_document(
        workspace_payload["id"], user["id"], "provider.pdf", [(1, "Evidence")]
    )
    monkeypatch.setattr(
        rag_service.retrieval_service, "search_workspace", lambda *args: chunks
    )
    with SessionLocal() as db:
        workspace = db.get(Workspace, UUID(workspace_payload["id"]))
        with pytest.raises(rag_service.RAGError) as raised:
            rag_service.answer_question(
                db,
                workspace,
                user["id"],
                "Question",
                5,
                None,
                UnusedEmbeddingProvider(),
                FailingProvider(),
            )
        assert raised.value.code == "LLM_PROVIDER_ERROR"
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(RAGResponseRecord).where(
                RAGResponseRecord.workspace_id == UUID(workspace_payload["id"])
            )
        ) == 0


def test_citation_migration_upgrade_downgrade_and_reupgrade(disposable_database, run_alembic):
    database_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    engine = create_engine(database_url)
    try:
        run_alembic("upgrade", "a72b19c64e31", database=disposable_database)
        run_alembic("upgrade", "head", database=disposable_database)
        with engine.connect() as connection:
            tables = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema='public'"
                    )
                ).scalars()
            )
            assert {"rag_responses", "rag_citations"}.issubset(tables)
        run_alembic("downgrade", "a72b19c64e31", database=disposable_database)
        with engine.connect() as connection:
            tables = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema='public'"
                    )
                ).scalars()
            )
            assert not {"rag_responses", "rag_citations"} & tables
        run_alembic("upgrade", "head", database=disposable_database)
    finally:
        engine.dispose()
