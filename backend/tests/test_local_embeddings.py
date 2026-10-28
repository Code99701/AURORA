import json
import math
import uuid
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.embeddings.base import (
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    EmbeddingProviderError,
)
from app.embeddings.local import (
    LocalEmbeddingProvider,
    resolve_embedding_device,
)
from app.models.user import User
from app.models.workspace import Workspace


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user_and_workspace(db_session):
    user = User(
        email=f"user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        display_name="Test User",
    )
    db_session.add(user)
    db_session.flush()

    workspace = Workspace(
        name=f"Workspace {uuid.uuid4().hex[:6]}",
        created_by=user.id,
    )
    db_session.add(workspace)
    db_session.flush()

    from app.models.workspace import WorkspaceMembership

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role="OWNER",
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(workspace)
    return user, workspace


def _fake_vector(seed: int = 1, dim: int = 768) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim).astype(np.float32)
    norm = np.linalg.norm(v)
    return v / norm


def test_local_provider_configuration_validation():
    with pytest.raises(EmbeddingConfigurationError, match="must not be blank"):
        LocalEmbeddingProvider(model_name="")

    with pytest.raises(EmbeddingConfigurationError, match="dimension must be 768"):
        LocalEmbeddingProvider(model_name="intfloat/multilingual-e5-base", dimension=384)


def test_device_resolution():
    assert resolve_embedding_device("cpu") == "cpu"

    with patch("torch.cuda.is_available", return_value=False):
        assert resolve_embedding_device("cuda") == "cpu"
        assert resolve_embedding_device(None) == "cpu"

    with patch("torch.cuda.is_available", return_value=True), patch(
        "torch.cuda.get_device_name", return_value="NVIDIA RTX 4060 Laptop"
    ):
        assert resolve_embedding_device("cuda") == "cuda"
        assert resolve_embedding_device(None) == "cuda"


def test_e5_prefix_conventions():
    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)
    mock_model = MagicMock()
    v1 = _fake_vector(1)
    v2 = _fake_vector(2)
    mock_model.encode.return_value = np.array([v1, v2])
    provider._model = mock_model

    # embed_documents must prepend 'passage: '
    results = provider.embed_documents(["First chunk", "Second chunk"])
    assert len(results) == 2
    mock_model.encode.assert_called_once()
    passed_args = mock_model.encode.call_args[0][0]
    assert passed_args == ["passage: First chunk", "passage: Second chunk"]

    # embed_query must prepend 'query: '
    mock_model.reset_mock()
    mock_model.encode.return_value = np.array([v1])
    q_result = provider.embed_query("What is backpropagation?")
    assert len(q_result) == 768
    passed_args = mock_model.encode.call_args[0][0]
    assert passed_args == ["query: What is backpropagation?"]


def test_local_provider_dimension_and_normalization():
    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)
    mock_model = MagicMock()
    # Unnormalized raw output
    raw = np.array([_fake_vector(42) * 5.0])
    mock_model.encode.return_value = raw
    provider._model = mock_model

    result = provider.embed_query("test query")
    assert len(result) == 768
    # L2 magnitude must be strictly 1.0 (within float precision)
    magnitude = math.sqrt(sum(x * x for x in result))
    assert pytest.approx(magnitude, 1e-5) == 1.0
    assert all(math.isfinite(x) for x in result)


def test_cache_hits_and_prefix_isolation():
    provider = LocalEmbeddingProvider(device="cpu", cache_size=100)
    mock_model = MagicMock()
    v1 = _fake_vector(10)
    v2 = _fake_vector(20)
    mock_model.encode.side_effect = [np.array([v1]), np.array([v2])]
    provider._model = mock_model

    # 1. Embed query
    res1 = provider.embed_query("identical text")
    assert mock_model.encode.call_count == 1

    # 2. Embed identical query again -> MUST HIT CACHE (encode call count unchanged)
    res2 = provider.embed_query("identical text")
    assert mock_model.encode.call_count == 1
    assert res1 == res2

    # 3. Embed identical text as a document passage -> MUST MISS CACHE (different prefix: 'passage: ' vs 'query: ')
    res3 = provider.embed_documents(["identical text"])[0]
    assert mock_model.encode.call_count == 2
    assert res3 == pytest.approx(v2.tolist(), abs=1e-6)


def test_cache_model_isolation():
    provider_a = LocalEmbeddingProvider(model_name="model-alpha", device="cpu", cache_size=100)
    provider_b = LocalEmbeddingProvider(model_name="model-beta", device="cpu", cache_size=100)

    key_a = provider_a._build_cache_key("query: ", "same text")
    key_b = provider_b._build_cache_key("query: ", "same text")
    assert key_a != key_b
    assert key_a.startswith("model-alpha:768:query: ")
    assert key_b.startswith("model-beta:768:query: ")


def test_cache_lru_bounded_eviction():
    provider = LocalEmbeddingProvider(device="cpu", cache_size=2)
    mock_model = MagicMock()
    mock_model.encode.side_effect = [
        np.array([_fake_vector(1)]),
        np.array([_fake_vector(2)]),
        np.array([_fake_vector(3)]),
    ]
    provider._model = mock_model

    provider.embed_query("item 1")
    provider.embed_query("item 2")
    assert len(provider._cache) == 2

    # Inserting 3rd item should evict "item 1"
    provider.embed_query("item 3")
    assert len(provider._cache) == 2

    # "item 1" should be evicted
    k1 = provider._build_cache_key("query: ", "item 1")
    k2 = provider._build_cache_key("query: ", "item 2")
    k3 = provider._build_cache_key("query: ", "item 3")
    assert k1 not in provider._cache
    assert k2 in provider._cache
    assert k3 in provider._cache


def test_partial_cache_hit_batching():
    provider = LocalEmbeddingProvider(device="cpu", cache_size=100)
    mock_model = MagicMock()
    v1 = _fake_vector(1)
    v2 = _fake_vector(2)
    v3 = _fake_vector(3)
    mock_model.encode.side_effect = [
        np.array([v1, v2]),  # first call: items 1 and 2
        np.array([v3]),      # second call: only item 3
    ]
    provider._model = mock_model

    provider.embed_documents(["text 1", "text 2"])
    assert mock_model.encode.call_count == 1

    # Now request text 2 (cached) and text 3 (new)
    res = provider.embed_documents(["text 2", "text 3"])
    assert mock_model.encode.call_count == 2
    # Only "text 3" was passed to encode on the second call
    assert mock_model.encode.call_args[0][0] == ["passage: text 3"]
    assert len(res) == 2
    assert res[0] == pytest.approx(v2.tolist())
    assert res[1] == pytest.approx(v3.tolist())


def test_embedding_error_wrapping():
    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)
    mock_model = MagicMock()
    mock_model.encode.side_effect = RuntimeError("CUDA out of memory")
    provider._model = mock_model

    with pytest.raises(EmbeddingProviderError, match="Local embedding inference failed"):
        provider.embed_query("failing query")


# ---------------------------------------------------------------------------
# Multilingual Retrieval Evaluation
# ---------------------------------------------------------------------------

def test_multilingual_semantic_similarity():
    """Verify that E5 embeddings map semantic equivalents closer than non-equivalents."""
    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)
    mock_model = MagicMock()

    # Create synthetic vectors where en_q is close to en_doc and hi_doc, far from unrelated
    base_v = _fake_vector(100)
    en_doc = base_v + 0.05 * _fake_vector(101)
    en_doc = en_doc / np.linalg.norm(en_doc)

    hi_doc = base_v + 0.08 * _fake_vector(102)
    hi_doc = hi_doc / np.linalg.norm(hi_doc)

    unrelated_doc = _fake_vector(999)

    q_vec = base_v.copy()

    mock_model.encode.side_effect = [
        np.array([q_vec]),
        np.array([en_doc, hi_doc, unrelated_doc]),
    ]
    provider._model = mock_model

    q_emb = provider.embed_query("machine learning fundamentals")
    docs = provider.embed_documents([
        "Introduction to machine learning algorithms and neural networks.",
        "मशीन लर्निंग एल्गोरिदम और न्यूरल नेटवर्क का परिचय।",
        "The recipe for chocolate chip cookies requires flour and sugar.",
    ])

    sim_en = float(np.dot(q_emb, docs[0]))
    sim_hi = float(np.dot(q_emb, docs[1]))
    sim_unrelated = float(np.dot(q_emb, docs[2]))

    # Cross-lingual Hindi document should have strong similarity, far higher than unrelated
    assert sim_en > 0.90
    assert sim_hi > 0.85
    assert sim_hi > sim_unrelated + 0.30


# ---------------------------------------------------------------------------
# Mixed-Model Retrieval Guard Tests
# ---------------------------------------------------------------------------

def test_retrieval_guard_rejects_mixed_models(db_session, test_user_and_workspace):
    test_user, test_workspace = test_user_and_workspace
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.services.retrieval import RetrievalError, search_workspace

    doc = Document(
        workspace_id=test_workspace.id,
        uploaded_by=test_user.id,
        original_filename="gemini_doc.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        file_size=1000,
        checksum="a" * 64,
        content_type="application/pdf",
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="gemini-embedding-001",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        page_chunk_index=0,
        text="Sample indexed text",
        character_count=19,
        approximate_token_count=5,
        embedding=_fake_vector(1).tolist(),
        embedding_model="gemini-embedding-001",
    )
    db_session.add(chunk)
    db_session.commit()

    # Search with LocalEmbeddingProvider ('intfloat/multilingual-e5-base') against a gemini index
    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)
    provider._model = MagicMock()
    provider._model.encode.return_value = np.array([_fake_vector(1)])

    with pytest.raises(RetrievalError) as exc_info:
        search_workspace(db_session, test_workspace, "test query", top_k=5, provider=provider)

    assert exc_info.value.code == "INDEX_MODEL_MISMATCH"
    assert "gemini-embedding-001" in exc_info.value.public_message
    assert "intfloat/multilingual-e5-base" in exc_info.value.public_message


# ---------------------------------------------------------------------------
# Migration, In-Place Citation Preservation, and Rollback Tests
# ---------------------------------------------------------------------------

def test_in_place_migration_preserves_citations(db_session, test_user_and_workspace, tmp_path):
    test_user, test_workspace = test_user_and_workspace
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.extracted_page import ExtractedPage
    from app.models.rag_response import RAGResponseRecord
    from app.models.rag_citation import RAGCitation
    from app.services.embedding_migration import migrate_document_embeddings

    doc = Document(
        workspace_id=test_workspace.id,
        uploaded_by=test_user.id,
        original_filename="citation_doc.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        file_size=1000,
        checksum="b" * 64,
        content_type="application/pdf",
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="gemini-embedding-001",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    page = ExtractedPage(
        document_id=doc.id,
        page_number=1,
        text="Section 1: Critical architectural specifications for AURORA.",
        character_count=60,
    )
    db_session.add(page)
    db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        extracted_page_id=page.id,
        page_number=1,
        chunk_index=0,
        page_chunk_index=0,
        page_start=1,
        page_end=1,
        context_prefix="",
        text="Section 1: Critical architectural specifications for AURORA.",
        character_count=60,
        approximate_token_count=10,
        embedding=_fake_vector(1).tolist(),
        embedding_model="gemini-embedding-001",
    )
    db_session.add(chunk)
    db_session.flush()
    original_chunk_id = chunk.id

    # Create RAG Response and Citation pointing to this chunk
    response_rec = RAGResponseRecord(
        workspace_id=test_workspace.id,
        requested_by=test_user.id,
        query="What are the specifications?",
        answer="The specifications are in Section 1.",
        top_k=5,
        citation_count=1,
        model="ollama/qwen3:8b",
    )
    db_session.add(response_rec)
    db_session.flush()

    citation = RAGCitation(
        response_id=response_rec.id,
        chunk_id=chunk.id,
        position=1,
        similarity=0.92,
    )
    db_session.add(citation)
    db_session.commit()

    # Migrate using mock LocalEmbeddingProvider
    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)
    new_v = _fake_vector(99)
    provider._model = MagicMock()
    provider._model.encode.return_value = np.array([new_v])

    result = migrate_document_embeddings(
        db=db_session,
        document=doc,
        provider=provider,
        dry_run=False,
        backup_dir=tmp_path,
    )

    assert result.status == "SUCCESS"
    assert result.in_place_updated is True
    assert result.backup_path is not None

    # Verify chunk was updated IN-PLACE: chunk.id MUST BE UNCHANGED
    db_session.refresh(chunk)
    assert chunk.id == original_chunk_id
    assert chunk.embedding_model == "intfloat/multilingual-e5-base"
    assert np.allclose(chunk.embedding, new_v, atol=1e-5)

    # Verify RAGCitation was NOT deleted or cascaded!
    db_citation = db_session.scalar(select(RAGCitation).where(RAGCitation.id == citation.id))
    assert db_citation is not None
    assert db_citation.chunk_id == original_chunk_id


def test_migration_manifest_and_rollback(db_session, test_user_and_workspace, tmp_path):
    test_user, test_workspace = test_user_and_workspace
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.extracted_page import ExtractedPage
    from app.services.embedding_migration import (
        migrate_document_embeddings,
        restore_embeddings_from_manifest,
    )

    doc = Document(
        workspace_id=test_workspace.id,
        uploaded_by=test_user.id,
        original_filename="rollback_doc.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        file_size=500,
        checksum="c" * 64,
        content_type="application/pdf",
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="gemini-embedding-001",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    page = ExtractedPage(
        document_id=doc.id,
        page_number=1,
        text="Content for rollback test.",
        character_count=26,
    )
    db_session.add(page)
    db_session.flush()

    original_vec = _fake_vector(77)
    chunk = DocumentChunk(
        document_id=doc.id,
        extracted_page_id=page.id,
        page_number=1,
        chunk_index=0,
        page_chunk_index=0,
        page_start=1,
        page_end=1,
        context_prefix="",
        text="Content for rollback test.",
        character_count=26,
        approximate_token_count=5,
        embedding=original_vec.tolist(),
        embedding_model="gemini-embedding-001",
    )
    db_session.add(chunk)
    db_session.commit()

    # 1. Migrate with backup
    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)
    migrated_vec = _fake_vector(88)
    provider._model = MagicMock()
    provider._model.encode.return_value = np.array([migrated_vec])

    result = migrate_document_embeddings(
        db=db_session,
        document=doc,
        provider=provider,
        dry_run=False,
        backup_dir=tmp_path,
    )
    assert result.status == "SUCCESS"
    manifest_file = result.backup_path

    # Verify migrated in DB
    db_session.refresh(chunk)
    assert chunk.embedding_model == "intfloat/multilingual-e5-base"

    # 2. Roll back using manifest
    restore_res = restore_embeddings_from_manifest(db_session, manifest_file)
    assert restore_res["status"] == "RESTORED"

    # Verify restored in DB
    db_session.refresh(chunk)
    db_session.refresh(doc)
    assert chunk.embedding_model == "gemini-embedding-001"
    assert doc.embedding_model == "gemini-embedding-001"
    assert np.allclose(chunk.embedding, original_vec, atol=1e-5)


def test_tampered_manifest_rejection(db_session, test_user_and_workspace, tmp_path):
    test_user, test_workspace = test_user_and_workspace
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.services.embedding_migration import (
        create_recovery_manifest,
        restore_embeddings_from_manifest,
    )

    doc = Document(
        workspace_id=test_workspace.id,
        uploaded_by=test_user.id,
        original_filename="tamper_doc.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        file_size=500,
        checksum="d" * 64,
        content_type="application/pdf",
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="gemini-embedding-001",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        page_chunk_index=0,
        text="Text",
        character_count=4,
        approximate_token_count=1,
        embedding=_fake_vector(1).tolist(),
        embedding_model="gemini-embedding-001",
    )
    db_session.add(chunk)
    db_session.commit()

    manifest_path = create_recovery_manifest(doc, [chunk], backup_dir=tmp_path)

    # Tamper with manifest vectors without updating checksum
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["chunks"][0]["embedding"][0] += 0.5
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    # Rollback must abort with ValueError
    with pytest.raises(ValueError, match="Manifest vector checksum mismatch"):
        restore_embeddings_from_manifest(db_session, manifest_path)

