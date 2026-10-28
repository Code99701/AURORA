import uuid
from unittest.mock import MagicMock
import pytest

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.embeddings.local import LocalEmbeddingProvider
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.extracted_page import ExtractedPage
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.services.retrieval import (
    detect_targeted_document,
    extract_page_range,
    search_workspace,
)
from app.services.rag import (
    is_model_refusal,
    persist_prepared_answer,
    RAGPreparation,
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_setup(db_session):
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

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role="OWNER",
    )
    db_session.add(membership)
    db_session.commit()

    return user, workspace


def test_extract_page_range_patterns():
    # 'first N pages'
    assert extract_page_range("give the explanation of first 5 pages of the pdf") == (1, 5)
    assert extract_page_range("Explain the first 10 pages please") == (1, 10)
    assert extract_page_range("first 1 page") == (1, 1)

    # 'pages X to Y' or 'pages X-Y'
    assert extract_page_range("summarise pages 2 to 6") == (2, 6)
    assert extract_page_range("what is in page 3-5?") == (3, 5)

    # single page
    assert extract_page_range("what is written on page 4 of the resume?") == (4, 4)
    assert extract_page_range("details on pages 12") == (12, 12)

    # non-page queries
    assert extract_page_range("summarize the entire document") is None
    assert extract_page_range("which skills appear most often?") is None


def test_detect_targeted_document():
    doc1 = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        uploaded_by=1,
        original_filename="Arnav_Mahajan_Resume.pdf",
        storage_provider="local",
        storage_key="test1.pdf",
        content_type="application/pdf",
        file_size=1000,
        checksum="a" * 64,
        status="PROCESSED",
        indexing_status="INDEXED",
    )
    doc2 = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        uploaded_by=1,
        original_filename="ANN_PPT_UNIT_2.pdf",
        storage_provider="local",
        storage_key="test2.pdf",
        content_type="application/pdf",
        file_size=1000,
        checksum="b" * 64,
        status="PROCESSED",
        indexing_status="INDEXED",
    )
    docs = [doc1, doc2]

    # Exact or stem match
    assert detect_targeted_document("What skills are in Arnav_Mahajan_Resume.pdf?", docs) == doc1
    assert detect_targeted_document("Summarize the ANN_PPT_UNIT_2 slides", docs) == doc2
    assert detect_targeted_document("Tell me about the resume details", docs) == doc1

    # Unrelated
    assert detect_targeted_document("What is machine learning?", docs) is None


def test_positional_retrieval_returns_ordered_chunks(db_session, test_setup):
    user, workspace = test_setup

    doc = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="slides_manual.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        file_size=1000,
        checksum="c" * 64,
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="intfloat/multilingual-e5-base",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    # Create 10 sequential pages
    for p in range(1, 11):
        chunk = DocumentChunk(
            document_id=doc.id,
            page_number=p,
            page_start=p,
            page_end=p,
            chunk_index=p - 1,
            page_chunk_index=0,
            text=f"Content for page {p} discussing topic {p}.",
            character_count=35,
            approximate_token_count=8,
            embedding=[0.01 * p] * 768,
            embedding_model="intfloat/multilingual-e5-base",
        )
        db_session.add(chunk)
    db_session.commit()

    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)

    # Query for first 3 pages
    results = search_workspace(
        db=db_session,
        workspace=workspace,
        query="give the explanation of first 3 pages of the slides",
        top_k=5,
        provider=provider,
    )

    # Must return pages 1, 2, 3 in sequential order!
    assert len(results) == 3
    assert results[0].page_number == 1
    assert results[1].page_number == 2
    assert results[2].page_number == 3
    assert "page 1" in results[0].text
    assert "page 2" in results[1].text
    assert "page 3" in results[2].text
    assert results[0].similarity > 0.90


def test_overview_retrieval_samples_across_document(db_session, test_setup):
    user, workspace = test_setup

    doc = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="large_book.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        file_size=5000,
        checksum="d" * 64,
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="intfloat/multilingual-e5-base",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    # Create 20 chunks
    for i in range(20):
        chunk = DocumentChunk(
            document_id=doc.id,
            page_number=i + 1,
            page_start=i + 1,
            page_end=i + 1,
            chunk_index=i,
            page_chunk_index=0,
            text=f"Chapter {i}: Detailed analysis of section {i}.",
            character_count=40,
            approximate_token_count=10,
            embedding=[0.02 * (i + 1)] * 768,
            embedding_model="intfloat/multilingual-e5-base",
        )
        db_session.add(chunk)
    db_session.commit()

    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)

    results = search_workspace(
        db=db_session,
        workspace=workspace,
        query="can you provide a summary of this document",
        top_k=4,
        provider=provider,
    )

    # Should sample chunks spanning the entire document (e.g. chunks 0, 5, 10, 15)
    assert len(results) == 4
    assert results[0].page_number == 1
    assert results[-1].page_number > 10


def test_honest_refusal_detection_and_citation_suppression(db_session, test_setup):
    user, workspace = test_setup

    # Test refusal phrase detection
    assert is_model_refusal("I couldn't find enough information in your authorized documents to answer this reliably.")
    assert is_model_refusal("The provided context does not contain information about salary.")
    assert not is_model_refusal("Based on Section 1, the architecture uses PostgreSQL.")

    # Create fake preparation with evidence
    fake_chunk = MagicMock()
    fake_chunk.chunk_id = uuid.uuid4()
    fake_chunk.document_id = uuid.uuid4()
    fake_chunk.filename = "test.pdf"
    fake_chunk.page_number = 1
    fake_chunk.similarity = 0.85
    fake_chunk.locator = None
    fake_chunk.extraction_method = "NATIVE"

    prep = RAGPreparation(
        query="What is the CEO salary?",
        answer_language=None,
        top_k=5,
        evidence=(fake_chunk,),
        prompt=MagicMock(),
    )

    # Persist with explicit refusal answer
    res = persist_prepared_answer(
        db=db_session,
        workspace=workspace,
        requested_by=user.id,
        preparation=prep,
        answer="I couldn't find enough information in the provided context to answer this reliably.",
        model="ollama/qwen3:8b",
        commit=True,
    )

    # Must flag insufficient_evidence = True and suppress citations!
    assert res.insufficient_evidence is True
    assert len(res.sources) == 0
