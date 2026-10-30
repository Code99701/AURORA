"""Regression tests for General-Purpose Document Coverage Architecture.

Covers:
1. Document alias resolution:
   - "Unit 1" resolving "Unit I.pptx"
   - "Part 2" resolving "Part II.docx"
   - Roman <-> Arabic numeral bidirectional normalization
   - Non-destructive stopword handling for structural terms ("unit", "part", "chapter")
2. Full-document intent detection:
   - "What is present in this document? Cover all pages starting from page 1."
   - "List all slides and their topics."
   - "Explain the document section by section."
   - Differentiation of overview/coverage requests from ordinary factual questions.
3. General coverage service:
   - Ordered batching for long documents without gaps
   - Single-pass coverage for compact documents
   - Real page and slide citation metadata preservation
   - Transparent reporting of missing/empty content units
   - Strict workspace and document isolation (zero cross-document leakage)
4. Preservation of ordinary RAG:
   - Targeted factual queries continue to use semantic retrieval without invoking full coverage.
"""

import uuid
import pytest

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.embeddings.local import LocalEmbeddingProvider
from app.models.content_unit import ContentUnit
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.ingestion_run import IngestionRun
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.rag.understanding import (
    normalize_numerals_in_text,
    resolve_target_documents,
    understand_query,
)
from app.services.coverage import (
    CoverageBatch,
    DocumentCoveragePlan,
    build_coverage_prompt,
    plan_document_coverage,
)
from app.services.rag import prepare_question
from app.services.retrieval import detect_targeted_document


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
        email=f"coverage_user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        display_name="Coverage User",
    )
    db_session.add(user)
    db_session.flush()

    workspace = Workspace(
        name=f"Coverage Workspace {uuid.uuid4().hex[:6]}",
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


def _create_ingestion_run(db, doc: Document, unit_count: int = 1) -> IngestionRun:
    ext = doc.original_filename.rsplit(".", 1)[-1].lower() if "." in doc.original_filename else "pdf"
    run = IngestionRun(
        document_id=doc.id,
        version=1,
        adapter_id=f"test.{ext}",
        adapter_version="1.0",
        source_format=ext,
        status="ACTIVE",
        outcome="COMPLETE",
        unit_count=unit_count,
        diagnostics={"usable_unit_count": unit_count},
    )
    db.add(run)
    db.flush()
    return run


# ---------------------------------------------------------------------------
# 1. Document Alias Resolution Tests
# ---------------------------------------------------------------------------

def test_numeral_normalization_bidirectional():
    """Verify Roman and Arabic numeral normalization."""
    # Arabic to Roman equivalents
    assert "unit i" in normalize_numerals_in_text("unit 1")
    assert "part ii" in normalize_numerals_in_text("part 2")
    assert "chapter iv" in normalize_numerals_in_text("chapter 4")

    # Roman to Arabic equivalents
    assert "unit 1" in normalize_numerals_in_text("unit i")
    assert "part 2" in normalize_numerals_in_text("part ii")
    assert "module 3" in normalize_numerals_in_text("module iii")


def test_alias_resolution_unit_1_to_unit_i():
    """Verify 'Unit 1' query successfully resolves 'Unit I.pptx'."""
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        uploaded_by=1,
        original_filename="Unit I.pptx",
        storage_provider="local",
        storage_key="test/unit_i.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size=50000,
        checksum="u1" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
    )
    docs = [doc]

    matched_doc = detect_targeted_document(
        query="what is present in UNIT 1 pdf i just uploaded cover all pages starting from 1",
        documents=docs,
    )
    assert matched_doc is not None
    assert matched_doc.id == doc.id
    assert matched_doc.original_filename == "Unit I.pptx"

    matches = resolve_target_documents(
        query="what is present in UNIT 1 pdf i just uploaded cover all pages starting from 1",
        indexed_documents=docs,
    )
    assert len(matches) > 0
    assert matches[0].document_id == doc.id


def test_alias_resolution_part_2_to_part_ii():
    """Verify 'Part 2' query successfully resolves 'Part II.docx'."""
    doc1 = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        uploaded_by=1,
        original_filename="Part II.docx",
        storage_provider="local",
        storage_key="test/part_ii.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=25000,
        checksum="p2" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
    )
    doc_other = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        uploaded_by=1,
        original_filename="Annual_Report_2025.pdf",
        storage_provider="local",
        storage_key="test/annual.pdf",
        content_type="application/pdf",
        file_size=15000,
        checksum="ar" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
    )
    docs = [doc1, doc_other]

    matched = detect_targeted_document(
        query="Give me a complete summary of part 2 document",
        documents=docs,
    )
    assert matched is not None
    assert matched.id == doc1.id
    assert matched.original_filename == "Part II.docx"


def test_alias_resolution_preserves_structural_keywords():
    """Verify keywords like unit, part, chapter are preserved and correctly routed."""
    doc_unit_1 = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        uploaded_by=1,
        original_filename="Unit I.pptx",
        storage_provider="local",
        storage_key="test/unit_i.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size=50000,
        checksum="u1" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
    )
    doc_unit_2 = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        uploaded_by=1,
        original_filename="Unit II.pptx",
        storage_provider="local",
        storage_key="test/unit_ii.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size=50000,
        checksum="u2" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
    )
    docs = [doc_unit_1, doc_unit_2]

    # Query specifically targeting unit 1 must match doc_unit_1, not doc_unit_2
    matched_1 = detect_targeted_document("Summarize Unit 1", docs)
    assert matched_1 is not None
    assert matched_1.id == doc_unit_1.id

    # Query targeting unit 2 must match doc_unit_2
    matched_2 = detect_targeted_document("Summarize Unit 2", docs)
    assert matched_2 is not None
    assert matched_2.id == doc_unit_2.id


# ---------------------------------------------------------------------------
# 2. Full-Document Intent Detection Tests
# ---------------------------------------------------------------------------

def test_full_document_intent_patterns():
    """Verify various natural language requests for full coverage are recognized."""
    queries_full_coverage = [
        "what is present in this document? cover all pages starting from page 1.",
        "what is present in UNIT 1 pdf i just uploaded cover all pages starting from 1",
        "List all slides and their topics.",
        "list every slide in the presentation with its title",
        "Give me a page-by-page explanation of the entire document",
        "walk through the entire presentation slide by slide",
        "Provide an inventory of all sections in this report",
        "Explain the whole document from start to end",
    ]

    for q in queries_full_coverage:
        intent = understand_query(q)
        assert intent.is_full_coverage is True, f"Failed to detect full coverage for query: {q}"
        assert intent.task in ("DOCUMENT_OVERVIEW", "EXHAUSTIVE_LIST"), f"Unexpected task {intent.task} for: {q}"


def test_factual_query_not_marked_full_coverage():
    """Verify standard factual questions do NOT trigger full-document coverage."""
    factual_queries = [
        "What is gradient descent?",
        "Who is the author of the resume?",
        "What was the total revenue in Q3?",
        "Explain backpropagation algorithm",
        "Does this company support remote work?",
    ]

    for q in factual_queries:
        intent = understand_query(q)
        assert intent.is_full_coverage is False, f"Factual query falsely marked full coverage: {q}"
        assert intent.task == "FACTUAL", f"Expected FACTUAL task for query: {q}"


# ---------------------------------------------------------------------------
# 3. General Coverage Service & Ordered Batching Tests
# ---------------------------------------------------------------------------

def test_coverage_planning_ordered_batches_for_long_doc(db_session, test_setup):
    """Verify long documents are partitioned into ordered contiguous batches without gaps."""
    user, workspace = test_setup

    doc = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="Long_Syllabus.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        file_size=50000,
        checksum="ls" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="intfloat/multilingual-e5-base",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    run = _create_ingestion_run(db_session, doc, unit_count=30)

    # Create 30 pages of ContentUnits and DocumentChunks (~15,000 chars total)
    for p in range(1, 31):
        cu = ContentUnit(
            document_id=doc.id,
            ingestion_run_id=run.id,
            kind="PAGE",
            ordinal=p - 1,
            character_count=500,
            text=f"Page {p} covers deep topic number {p} in detail. " * 10,
            locator={"page": p},
            status="USABLE",
            extraction_method="native",
        )
        db_session.add(cu)
        db_session.flush()

        chunk = DocumentChunk(
            document_id=doc.id,
            content_unit_id=cu.id,
            page_number=p,
            page_start=p,
            page_end=p,
            chunk_index=p - 1,
            page_chunk_index=0,
            text=f"Page {p} covers deep topic number {p} in detail. " * 10,
            character_count=500,
            approximate_token_count=100,
            embedding=[0.01 * p] * 768,
            embedding_model="intfloat/multilingual-e5-base",
        )
        db_session.add(chunk)
    db_session.commit()

    # Plan coverage with a conservative batch limit of 4000 characters
    plan = plan_document_coverage(
        db=db_session,
        workspace=workspace,
        document=doc,
        max_single_pass_characters=6000,
        max_batch_characters=4000,
    )

    assert plan.total_chunks == 30
    assert plan.total_units == 30
    assert plan.is_multi_batch is True
    assert len(plan.batches) > 1

    # Verify contiguous batches without gaps
    expected_start = 1
    for i, batch in enumerate(plan.batches):
        assert batch.batch_index == i + 1
        assert batch.start_page == expected_start
        assert batch.end_page >= batch.start_page
        assert len(batch.chunks) > 0
        expected_start = batch.end_page + 1

    assert plan.batches[-1].end_page == 30


def test_coverage_planning_single_pass_for_short_doc(db_session, test_setup):
    """Verify compact documents fit in a single batch."""
    user, workspace = test_setup

    doc = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="Short_Notes.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        file_size=5000,
        checksum="sn" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="intfloat/multilingual-e5-base",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    run = _create_ingestion_run(db_session, doc, unit_count=3)

    for p in range(1, 4):
        cu = ContentUnit(
            document_id=doc.id,
            ingestion_run_id=run.id,
            kind="PAGE",
            ordinal=p - 1,
            character_count=200,
            text=f"Brief notes on topic {p}.",
            locator={"page": p},
            status="USABLE",
            extraction_method="native",
        )
        db_session.add(cu)
        db_session.flush()

        chunk = DocumentChunk(
            document_id=doc.id,
            content_unit_id=cu.id,
            page_number=p,
            page_start=p,
            page_end=p,
            chunk_index=p - 1,
            page_chunk_index=0,
            text=f"Brief notes on topic {p}.",
            character_count=200,
            approximate_token_count=40,
            embedding=[0.01 * p] * 768,
            embedding_model="intfloat/multilingual-e5-base",
        )
        db_session.add(chunk)
    db_session.commit()

    plan = plan_document_coverage(db=db_session, workspace=workspace, document=doc)
    assert plan.total_chunks == 3
    assert plan.is_multi_batch is False
    assert len(plan.batches) == 1
    assert plan.batches[0].start_page == 1
    assert plan.batches[0].end_page == 3


def test_transparent_reporting_of_empty_units(db_session, test_setup):
    """Verify empty/image-only content units are tracked and reported transparently."""
    user, workspace = test_setup

    doc = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="Presentation_With_Empty_Slides.pptx",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size=10000,
        checksum="es" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="intfloat/multilingual-e5-base",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    run = _create_ingestion_run(db_session, doc, unit_count=3)

    # Slide 1 has text, Slide 2 is blank/image-only, Slide 3 has text
    cu1 = ContentUnit(document_id=doc.id, ingestion_run_id=run.id, kind="SLIDE", ordinal=0, character_count=100, text="Slide 1 intro", locator={"slide": 1}, status="USABLE", extraction_method="native")
    cu2 = ContentUnit(document_id=doc.id, ingestion_run_id=run.id, kind="SLIDE", ordinal=1, character_count=0, text="", locator={"slide": 2}, status="SKIPPED", extraction_method="native")
    cu3 = ContentUnit(document_id=doc.id, ingestion_run_id=run.id, kind="SLIDE", ordinal=2, character_count=100, text="Slide 3 conclusion", locator={"slide": 3}, status="USABLE", extraction_method="native")
    db_session.add_all([cu1, cu2, cu3])
    db_session.flush()

    chunk1 = DocumentChunk(
        document_id=doc.id, content_unit_id=cu1.id, page_number=1, page_start=1, page_end=1,
        chunk_index=0, page_chunk_index=0, text="Slide 1 intro", character_count=100, approximate_token_count=20,
        embedding=[0.1] * 768, embedding_model="intfloat/multilingual-e5-base"
    )
    chunk3 = DocumentChunk(
        document_id=doc.id, content_unit_id=cu3.id, page_number=3, page_start=3, page_end=3,
        chunk_index=1, page_chunk_index=0, text="Slide 3 conclusion", character_count=100, approximate_token_count=20,
        embedding=[0.3] * 768, embedding_model="intfloat/multilingual-e5-base"
    )
    db_session.add_all([chunk1, chunk3])
    db_session.commit()

    plan = plan_document_coverage(db=db_session, workspace=workspace, document=doc)
    assert 2 in plan.empty_pages

    # Verify build_coverage_prompt includes transparency notice
    prompt = build_coverage_prompt(plan, "List all slides and their topics.")
    assert "2" in prompt.user_prompt
    assert "contained figures/media without extractable text" in prompt.user_prompt


def test_cross_document_isolation_in_coverage_plan(db_session, test_setup):
    """Verify coverage planning for one document never includes chunks from other workspace documents."""
    user, workspace = test_setup

    doc_target = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="Target_Doc.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        file_size=5000,
        checksum="td" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="intfloat/multilingual-e5-base",
        embedding_dimension=768,
    )
    doc_unrelated = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="Unrelated_Doc.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        file_size=5000,
        checksum="ud" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="intfloat/multilingual-e5-base",
        embedding_dimension=768,
    )
    db_session.add_all([doc_target, doc_unrelated])
    db_session.flush()

    run_target = _create_ingestion_run(db_session, doc_target, unit_count=2)
    run_unrelated = _create_ingestion_run(db_session, doc_unrelated, unit_count=2)

    # Target doc has 2 chunks
    for i in (1, 2):
        cu = ContentUnit(document_id=doc_target.id, ingestion_run_id=run_target.id, kind="PAGE", ordinal=i-1, character_count=50, text=f"Target doc page {i}", locator={"page": i}, status="USABLE", extraction_method="native")
        db_session.add(cu)
        db_session.flush()
        db_session.add(DocumentChunk(
            document_id=doc_target.id,
            content_unit_id=cu.id,
            page_number=i, page_start=i, page_end=i,
            chunk_index=i - 1, page_chunk_index=0, text=f"Target doc page {i}",
            character_count=50, approximate_token_count=10,
            embedding=[0.1] * 768, embedding_model="intfloat/multilingual-e5-base"
        ))

    # Unrelated doc has 2 chunks
    for i in (1, 2):
        cu = ContentUnit(document_id=doc_unrelated.id, ingestion_run_id=run_unrelated.id, kind="PAGE", ordinal=i-1, character_count=50, text=f"SECRET UNRELATED DATA {i}", locator={"page": i}, status="USABLE", extraction_method="native")
        db_session.add(cu)
        db_session.flush()
        db_session.add(DocumentChunk(
            document_id=doc_unrelated.id,
            content_unit_id=cu.id,
            page_number=i, page_start=i, page_end=i,
            chunk_index=i - 1, page_chunk_index=0, text=f"SECRET UNRELATED DATA {i}",
            character_count=50, approximate_token_count=10,
            embedding=[0.9] * 768, embedding_model="intfloat/multilingual-e5-base"
        ))
    db_session.commit()

    plan = plan_document_coverage(db=db_session, workspace=workspace, document=doc_target)

    # Must contain only target doc chunks
    assert plan.total_chunks == 2
    for chunk in plan.all_chunks:
        assert chunk.document_id == doc_target.id
        assert "SECRET UNRELATED DATA" not in chunk.text


def test_workspace_isolation_blocks_cross_workspace_access(db_session, test_setup):
    """Verify plan_document_coverage refuses access if document does not belong to workspace."""
    user, workspace = test_setup

    foreign_workspace = Workspace(
        name=f"Foreign Workspace {uuid.uuid4().hex[:6]}",
        created_by=user.id,
    )
    db_session.add(foreign_workspace)
    db_session.flush()

    foreign_doc = Document(
        workspace_id=foreign_workspace.id,
        uploaded_by=user.id,
        original_filename="Foreign_Doc.pdf",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        file_size=5000,
        checksum="fd" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
    )
    db_session.add(foreign_doc)
    db_session.commit()

    with pytest.raises(ValueError, match="Document does not belong to the authorized workspace"):
        plan_document_coverage(db=db_session, workspace=workspace, document=foreign_doc)


# ---------------------------------------------------------------------------
# 4. Preservation of Ordinary RAG vs Coverage Routing
# ---------------------------------------------------------------------------

def test_rag_routing_coverage_vs_factual(db_session, test_setup):
    """Verify that full-coverage requests route to coverage planning while factual queries preserve semantic retrieval."""
    user, workspace = test_setup

    doc = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="Unit I.pptx",
        storage_provider="local",
        storage_key=f"test/{uuid.uuid4()}.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size=20000,
        checksum="ui" * 32,
        status="PROCESSED",
        indexing_status="INDEXED",
        embedding_model="intfloat/multilingual-e5-base",
        embedding_dimension=768,
    )
    db_session.add(doc)
    db_session.flush()

    run = _create_ingestion_run(db_session, doc, unit_count=5)

    for s in range(1, 6):
        cu = ContentUnit(
            document_id=doc.id, ingestion_run_id=run.id, kind="SLIDE", ordinal=s-1, character_count=100, text=f"Slide {s} text", locator={"slide": s}, status="USABLE", extraction_method="native"
        )
        db_session.add(cu)
        db_session.flush()
        db_session.add(DocumentChunk(
            document_id=doc.id, content_unit_id=cu.id, page_number=s, page_start=s, page_end=s,
            chunk_index=s - 1, page_chunk_index=0, text=f"Slide {s} discussion about neural networks.",
            character_count=100, approximate_token_count=20,
            embedding=[0.05 * s] * 768, embedding_model="intfloat/multilingual-e5-base"
        ))
    db_session.commit()

    provider = LocalEmbeddingProvider(device="cpu", cache_size=0)

    # 1. Full coverage query targeting Unit I: must produce a coverage plan with ALL 5 slides
    prep_coverage = prepare_question(
        db=db_session,
        workspace=workspace,
        query="what is present in UNIT 1 pdf i just uploaded cover all pages starting from 1",
        top_k=3,
        answer_language=None,
        embedding_provider=provider,
    )
    assert prep_coverage.coverage_plan is not None
    assert prep_coverage.coverage_plan.total_chunks == 5
    assert len(prep_coverage.coverage_plan.all_chunks) == 5
    # All 5 slides present in sequential order
    assert [c.page_number for c in prep_coverage.coverage_plan.all_chunks] == [1, 2, 3, 4, 5]

    # 2. Targeted factual query: must NOT invoke coverage plan, using standard top_k semantic retrieval
    prep_factual = prepare_question(
        db=db_session,
        workspace=workspace,
        query="What are neural networks in Unit 1?",
        top_k=2,
        answer_language=None,
        embedding_provider=provider,
    )
    assert prep_factual.coverage_plan is None
    # Semantic retrieval bounded by top_k
    assert len(prep_factual.evidence) <= 2
