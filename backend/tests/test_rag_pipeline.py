import hashlib
import uuid
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.session import SessionLocal
from app.embeddings.base import EmbeddingConfigurationError, EmbeddingProviderError
from app.embeddings.deps import get_embedding_provider
from app.embeddings.gemini import GeminiEmbeddingProvider
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.extracted_page import ExtractedPage
from app.rag.chunking import chunk_text


class FakeEmbeddingProvider:
    provider_name = "fake"
    model_name = "fake-multilingual-v1"
    dimension = EMBEDDING_DIMENSION

    def __init__(self):
        self.document_calls = 0
        self.query_calls = 0

    @staticmethod
    def _vector(value: str) -> list[float]:
        lowered = value.casefold()
        vector = [0.0] * EMBEDDING_DIMENSION
        keywords = {
            "database": 0,
            "postgres": 0,
            "mountain": 1,
            "himalaya": 1,
            "bonjour": 2,
            "français": 2,
        }
        for keyword, axis in keywords.items():
            if keyword in lowered:
                vector[axis] += 1.0
        if not any(vector):
            axis = 10 + int(hashlib.sha256(lowered.encode()).hexdigest()[:4], 16) % 100
            vector[axis] = 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return [self._vector(value) for value in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls += 1
        return self._vector(text)


class WrongDimensionProvider(FakeEmbeddingProvider):
    dimension = 12


class WrongOutputProvider(FakeEmbeddingProvider):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] * 12 for _ in texts]


@pytest.fixture
def fake_provider():
    provider = FakeEmbeddingProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    try:
        yield provider
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)


def authenticated_client(email: str) -> tuple[TestClient, dict]:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "rag-pipeline-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "rag-pipeline-password"},
    )
    assert login.status_code == 200
    return client, registration.json()


def create_workspace(client: TestClient, name: str) -> dict:
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_processed_document(
    workspace_id: str,
    user_id: int,
    filename: str,
    pages: list[str],
) -> Document:
    with SessionLocal() as db:
        document = Document(
            workspace_id=UUID(workspace_id),
            uploaded_by=user_id,
            original_filename=filename,
            storage_provider="test",
            storage_key=f"tests/{uuid.uuid4()}.pdf",
            content_type="application/pdf",
            file_size=100,
            checksum="a" * 64,
            status="PROCESSED",
            page_count=len(pages),
        )
        db.add(document)
        db.flush()
        document_id = document.id
        db.add_all(
            ExtractedPage(
                document_id=document_id,
                page_number=number,
                text=page,
                character_count=len(page),
            )
            for number, page in enumerate(pages, start=1)
        )
        db.commit()
        db.refresh(document)
        db.expunge(document)
        return document


def index(client: TestClient, workspace_id: str, document_id: UUID):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/index"
    )


def search(client: TestClient, workspace_id: str, query: str, top_k: int = 5):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/search",
        json={"query": query, "top_k": top_k},
    )


def test_chunking_short_long_overlap_and_determinism():
    short = chunk_text("A short page.", chunk_size=40, overlap=8)
    assert [chunk.text for chunk in short] == ["A short page."]

    source = " ".join(f"word-{number:03d}" for number in range(80))
    first = chunk_text(source, chunk_size=120, overlap=20)
    second = chunk_text(source, chunk_size=120, overlap=20)
    assert first == second
    assert len(first) > 1
    assert [chunk.page_chunk_index for chunk in first] == list(range(len(first)))
    assert all(0 < chunk.character_count <= 120 for chunk in first)
    assert all(chunk.approximate_token_count == (len(chunk.text) + 3) // 4 for chunk in first)
    assert any(previous.text[-12:] in current.text for previous, current in zip(first, first[1:]))


def test_empty_pages_produce_no_chunks():
    assert chunk_text("", 1000, 150) == []
    assert chunk_text("   \n\n", 1000, 150) == []


def test_indexing_persists_page_aware_chunks_and_is_idempotent(fake_provider):
    client, user = authenticated_client("rag-index@example.com")
    workspace = create_workspace(client, "RAG indexing")
    document = create_processed_document(
        workspace["id"],
        user["id"],
        "multilingual.pdf",
        ["database " * 180, "", "bonjour français"],
    )

    response = index(client, workspace["id"], document.id)
    assert response.status_code == 200
    payload = response.json()
    assert payload["indexing_status"] == "INDEXED"
    assert payload["embedding_model"] == fake_provider.model_name
    assert payload["embedding_dimension"] == EMBEDDING_DIMENSION
    assert payload["indexed_at"] is not None

    with SessionLocal() as db:
        chunks = db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        ).all()
        original_ids = [chunk.id for chunk in chunks]
        assert len(chunks) > 2
        assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
        assert {chunk.page_number for chunk in chunks} == {1, 3}
        assert all(len(chunk.embedding) == EMBEDDING_DIMENSION for chunk in chunks)

    repeated = index(client, workspace["id"], document.id)
    assert repeated.status_code == 200
    assert fake_provider.document_calls == 1
    with SessionLocal() as db:
        assert db.scalars(
            select(DocumentChunk.id)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        ).all() == original_ids


def test_indexing_requires_processed_document(fake_provider):
    client, user = authenticated_client("rag-unprocessed@example.com")
    workspace = create_workspace(client, "Unprocessed")
    document = create_processed_document(
        workspace["id"], user["id"], "unprocessed.pdf", ["database"]
    )
    with SessionLocal() as db:
        stored = db.get(Document, document.id)
        stored.status = "UPLOADED"
        db.commit()
    response = index(client, workspace["id"], document.id)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DOCUMENT_NOT_PROCESSED"


def test_embedding_configuration_and_dimension_fail_safely():
    with pytest.raises(EmbeddingConfigurationError, match="API key"):
        GeminiEmbeddingProvider(None, "gemini-embedding-001", EMBEDDING_DIMENSION)

    provider = WrongDimensionProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    try:
        client, user = authenticated_client("rag-dimension@example.com")
        workspace = create_workspace(client, "Dimension mismatch")
        document = create_processed_document(
            workspace["id"], user["id"], "wrong-dimension.pdf", ["database"]
        )
        response = index(client, workspace["id"], document.id)
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "EMBEDDING_DIMENSION_MISMATCH"


def test_gemini_embedding_provider_batches_large_documents(monkeypatch):
    batch_sizes: list[int] = []

    class FakeResponse:
        status_code = 200
        headers: dict[str, str] = {}

        def __init__(self, size: int):
            self.size = size

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "embeddings": [
                    {"values": [1.0, 0.0, 0.0]}
                    for _ in range(self.size)
                ]
            }

    def fake_post(url, *, headers, json, timeout):
        requests = json["requests"]
        batch_sizes.append(len(requests))
        assert len(requests) <= 100
        assert headers == {"x-goog-api-key": "test-key"}
        assert "test-key" not in url
        return FakeResponse(len(requests))

    monkeypatch.setattr("app.embeddings.gemini.httpx.post", fake_post)
    provider = GeminiEmbeddingProvider("test-key", "gemini-test", 3)

    vectors = provider.embed_documents([f"chunk {index}" for index in range(387)])

    assert batch_sizes == [100, 100, 100, 87]
    assert len(vectors) == 387
    assert vectors[0] == [1.0, 0.0, 0.0]


def test_gemini_embedding_provider_validates_each_batch_count(monkeypatch):
    calls = 0

    class FakeResponse:
        status_code = 200
        headers: dict[str, str] = {}

        def raise_for_status(self):
            return None

        def json(self):
            nonlocal calls
            calls += 1
            size = 100 if calls == 1 else 86
            return {
                "embeddings": [
                    {"values": [1.0, 0.0, 0.0]}
                    for _ in range(size)
                ]
            }

    monkeypatch.setattr(
        "app.embeddings.gemini.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )
    provider = GeminiEmbeddingProvider("test-key", "gemini-test", 3)

    with pytest.raises(EmbeddingProviderError, match="unexpected count"):
        provider.embed_documents([f"chunk {index}" for index in range(187)])


def test_gemini_embedding_provider_retries_quota_without_url_secret(monkeypatch):
    request = httpx.Request(
        "POST",
        "https://generativelanguage.googleapis.com/v1beta/models/test:batchEmbedContents",
    )
    responses = iter(
        [
            httpx.Response(
                429,
                request=request,
                json={
                    "error": {
                        "message": "Quota exhausted. Please retry in 12.5s.",
                        "status": "RESOURCE_EXHAUSTED",
                    }
                },
            ),
            httpx.Response(
                200,
                request=request,
                json={"embeddings": [{"values": [1.0, 0.0, 0.0]}]},
            ),
        ]
    )
    delays: list[float] = []

    def fake_post(url, *, headers, json, timeout):
        assert headers == {"x-goog-api-key": "test-key"}
        assert "test-key" not in url
        return next(responses)

    monkeypatch.setattr("app.embeddings.gemini.httpx.post", fake_post)
    monkeypatch.setattr("app.embeddings.gemini.time.sleep", delays.append)
    provider = GeminiEmbeddingProvider("test-key", "gemini-test", 3)

    vector = provider.embed_query("quota-safe query")

    assert vector == [1.0, 0.0, 0.0]
    assert delays == [13.5]


def test_wrong_provider_output_marks_indexing_failed():
    app.dependency_overrides[get_embedding_provider] = lambda: WrongOutputProvider()
    try:
        client, user = authenticated_client("rag-output-dimension@example.com")
        workspace = create_workspace(client, "Output dimension mismatch")
        document = create_processed_document(
            workspace["id"], user["id"], "wrong-output.pdf", ["database"]
        )
        response = index(client, workspace["id"], document.id)
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "EMBEDDING_DIMENSION_MISMATCH"
    with SessionLocal() as db:
        stored = db.get(Document, document.id)
        assert stored.indexing_status == "FAILED"
        assert stored.indexing_error == "EMBEDDING_DIMENSION_MISMATCH"


def test_semantic_search_ranks_limits_and_returns_provenance(fake_provider):
    client, user = authenticated_client("rag-search@example.com")
    workspace = create_workspace(client, "Semantic search")
    database_document = create_processed_document(
        workspace["id"], user["id"], "database-guide.pdf", ["Postgres database indexing"]
    )
    mountain_document = create_processed_document(
        workspace["id"], user["id"], "mountains.pdf", ["Himalaya mountain expedition"]
    )
    assert index(client, workspace["id"], database_document.id).status_code == 200
    assert index(client, workspace["id"], mountain_document.id).status_code == 200

    response = search(client, workspace["id"], "database", top_k=1)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["document_id"] == str(database_document.id)
    assert payload["items"][0]["filename"] == "database-guide.pdf"
    assert payload["items"][0]["page_number"] == 1
    assert payload["items"][0]["text"] == "Postgres database indexing"
    assert payload["items"][0]["similarity"] == pytest.approx(1.0)
    assert fake_provider.query_calls == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "   ", "top_k": 5},
        {"query": "database", "top_k": 0},
        {"query": "database", "top_k": 21},
        {"query": "database", "top_k": 5, "extra": True},
    ],
)
def test_search_request_validation(fake_provider, payload):
    client, _ = authenticated_client(f"rag-validation-{uuid.uuid4()}@example.com")
    workspace = create_workspace(client, "Search validation")
    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/search", json=payload
    )
    assert response.status_code == 422


def test_retrieval_is_workspace_scoped_and_nonmembers_are_concealed(fake_provider):
    owner, owner_user = authenticated_client("rag-owner@example.com")
    outsider, _ = authenticated_client("rag-outsider@example.com")
    first = create_workspace(owner, "First private workspace")
    second = create_workspace(owner, "Second private workspace")
    first_document = create_processed_document(
        first["id"], owner_user["id"], "first.pdf", ["database first private"]
    )
    second_document = create_processed_document(
        second["id"], owner_user["id"], "second.pdf", ["database second private"]
    )
    assert index(owner, first["id"], first_document.id).status_code == 200
    assert index(owner, second["id"], second_document.id).status_code == 200

    response = search(owner, first["id"], "database", top_k=10)
    assert response.status_code == 200
    assert {item["document_id"] for item in response.json()["items"]} == {
        str(first_document.id)
    }
    assert search(outsider, first["id"], "database").status_code == 404
    assert index(owner, second["id"], first_document.id).status_code == 404


def test_document_deletion_cascades_chunks(fake_provider):
    client, user = authenticated_client("rag-cascade@example.com")
    workspace = create_workspace(client, "Chunk cascade")
    document = create_processed_document(
        workspace["id"], user["id"], "cascade.pdf", ["database cascade"]
    )
    assert index(client, workspace["id"], document.id).status_code == 200
    with SessionLocal() as db:
        stored = db.get(Document, document.id)
        db.delete(stored)
        db.commit()
        assert db.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == document.id
            )
        ) == 0


def test_provider_errors_do_not_expose_private_details():
    class FailingProvider(FakeEmbeddingProvider):
        def embed_documents(self, texts):
            raise EmbeddingProviderError("secret provider payload")

    app.dependency_overrides[get_embedding_provider] = lambda: FailingProvider()
    try:
        client, user = authenticated_client("rag-provider-error@example.com")
        workspace = create_workspace(client, "Provider failure")
        document = create_processed_document(
            workspace["id"], user["id"], "provider.pdf", ["database"]
        )
        response = index(client, workspace["id"], document.id)
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "EMBEDDING_PROVIDER_ERROR"
    assert "secret provider payload" not in response.text
    with SessionLocal() as db:
        stored = db.get(Document, document.id)
        assert stored.indexing_status == "FAILED"
        assert stored.indexing_error == "EMBEDDING_PROVIDER_ERROR"


def test_rag_migration_upgrade_downgrade_and_reupgrade(disposable_database, run_alembic):
    database_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    migration_engine = create_engine(database_url)
    try:
        run_alembic("upgrade", "f93d2ae61c84", database=disposable_database)
        run_alembic("upgrade", "head", database=disposable_database)
        with migration_engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM pg_extension WHERE extname = 'vector')"
                )
            ).scalar_one() is True
            assert connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='document_chunks')"
                )
            ).scalar_one() is True
            assert connection.execute(
                text(
                    "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
                    "JOIN pg_class c ON c.oid=a.attrelid "
                    "WHERE c.relname='document_chunks' AND a.attname='embedding'"
                )
            ).scalar_one() == "vector(768)"

        run_alembic("downgrade", "f93d2ae61c84", database=disposable_database)
        with migration_engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='document_chunks')"
                )
            ).scalar_one() is False
            columns = set(
                connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='documents'"
                    )
                ).scalars()
            )
            assert "indexing_status" not in columns
        run_alembic("upgrade", "head", database=disposable_database)
    finally:
        migration_engine.dispose()
