import re
from dataclasses import dataclass
from collections import defaultdict, deque

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.embeddings import EmbeddingDimensionError, EmbeddingProvider, EmbeddingProviderError
from app.embeddings.base import validate_and_normalize
from app.core.config import settings
from app.models.content_unit import ContentUnit
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.workspace import Workspace


from app.rag.understanding import (
    PageSlideConstraint,
    QueryIntent,
    extract_page_or_slide_constraint,
    resolve_target_documents,
    understand_query,
)


FIRST_N_PATTERN = re.compile(r"\bfirst\s+(\d+)\s+pages?\b", re.IGNORECASE)
PAGE_RANGE_PATTERN = re.compile(r"\bpages?\s+(\d+)\s*(?:to|-)\s*(\d+)\b", re.IGNORECASE)
SINGLE_PAGE_PATTERN = re.compile(r"\bpages?\s+(\d+)\b", re.IGNORECASE)

OVERVIEW_PATTERN = re.compile(
    r"\b(summar(y|ise|ize|izing)|overview|table of contents|outline|what is (this|the) (document|pdf|book|paper) about)\b",
    re.IGNORECASE,
)


def extract_page_range(query: str) -> tuple[int, int] | None:
    """Detect if user asks for specific page(s) or slide(s)."""
    constraint = extract_page_or_slide_constraint(query)
    if constraint:
        return (constraint.start, constraint.end)
    m1 = FIRST_N_PATTERN.search(query)
    if m1:
        n = int(m1.group(1))
        return (1, min(n, 50)) if n > 0 else None

    m2 = PAGE_RANGE_PATTERN.search(query)
    if m2:
        s, e = int(m2.group(1)), int(m2.group(2))
        return (s, min(e, s + 50)) if s > 0 and e >= s else None

    m3 = SINGLE_PAGE_PATTERN.search(query)
    if m3:
        p = int(m3.group(1))
        return (p, p) if p > 0 else None

    return None


def detect_targeted_document(query: str, documents: list[Document]) -> Document | None:
    """Check if the user explicitly mentioned a document filename, stem, or token in the query."""
    matches = resolve_target_documents(query, documents)
    if matches:
        target_id = matches[0].document_id
        return next((d for d in documents if d.id == target_id), None)

    q_lower = query.casefold()
    q_words = set(re.findall(r"\b[A-Za-z0-9_-]+\b", q_lower))

    for doc in documents:
        fname_lower = doc.original_filename.casefold()
        stem_lower = doc.original_filename.rsplit(".", 1)[0].casefold()

        # Direct substring match
        if fname_lower in q_lower or (len(stem_lower) >= 3 and stem_lower in q_lower):
            return doc

        # Token match on filename parts
        parts = [
            p for p in re.split(r"[-_\s]+", stem_lower)
            if len(p) >= 4 and p not in {"unit", "file", "test", "book", "data"}
        ]
        for part in parts:
            if part in q_words:
                return doc

    return None


class RetrievalError(Exception):
    def __init__(self, code: str, public_message: str, status_code: int):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: object
    document_id: object
    filename: str
    page_number: int | None
    text: str
    similarity: float
    locator: dict | None = None
    extraction_method: str | None = None


def _normalized_text(text: str) -> str:
    return " ".join(text.casefold().split())


def _diversify_candidates(
    candidates: list[RetrievedChunk],
    top_k: int,
    priority_doc_ids: list[object] | None = None,
) -> list[RetrievedChunk]:
    """Deduplicate within a document, then round-robin documents by best rank."""
    if priority_doc_ids:
        prioritized = [c for c in candidates if c.document_id in priority_doc_ids]
        if prioritized:
            candidates = prioritized

    unique: list[RetrievedChunk] = []
    seen_text: set[tuple[object, str]] = set()
    for item in candidates:
        fingerprint = (item.document_id, _normalized_text(item.text))
        if fingerprint in seen_text:
            continue
        seen_text.add(fingerprint)
        unique.append(item)

    queues: dict[object, deque[RetrievedChunk]] = defaultdict(deque)
    document_order: list[object] = []
    for item in unique:
        if item.document_id not in queues:
            document_order.append(item.document_id)
        queues[item.document_id].append(item)

    if priority_doc_ids:
        prioritized_docs = [doc_id for doc_id in priority_doc_ids if doc_id in queues]
        remaining = [doc_id for doc_id in document_order if doc_id not in prioritized_docs]
        document_order = prioritized_docs + remaining

    selected: list[RetrievedChunk] = []
    while len(selected) < top_k:
        added = False
        for document_id in document_order:
            if queues[document_id] and len(selected) < top_k:
                selected.append(queues[document_id].popleft())
                added = True
        if not added:
            break
    return selected


def has_research_ready_sources(
    db: Session, workspace: Workspace, provider_model: str | None = None
) -> bool:
    stmt = (
        select(DocumentChunk.id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.workspace_id == workspace.id,
            Document.indexing_status == "INDEXED",
        )
    )
    if provider_model:
        stmt = stmt.where(DocumentChunk.embedding_model == provider_model)
    ready_chunk = db.scalar(stmt.limit(1))
    return ready_chunk is not None


def search_workspace(
    db: Session,
    workspace: Workspace,
    query: str,
    top_k: int,
    provider: EmbeddingProvider,
    intent: QueryIntent | None = None,
) -> list[RetrievedChunk]:
    if not has_research_ready_sources(db, workspace):
        raise RetrievalError(
            "NO_RESEARCH_READY_SOURCES",
            "Process and index a workspace document before asking a grounded question",
            409,
        )
    if not has_research_ready_sources(db, workspace, provider_model=provider.model_name):
        existing_models = list(
            db.scalars(
                select(DocumentChunk.embedding_model)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    Document.workspace_id == workspace.id,
                    Document.indexing_status == "INDEXED",
                )
                .distinct()
            ).all()
        )
        models_str = ", ".join(f"'{m}'" for m in existing_models) if existing_models else "unknown"
        raise RetrievalError(
            "INDEX_MODEL_MISMATCH",
            f"Workspace documents were indexed with {models_str}, but the active search provider uses '{provider.model_name}'. Re-index workspace documents before querying.",
            409,
        )
    if provider.dimension != EMBEDDING_DIMENSION:
        raise RetrievalError(
            "EMBEDDING_DIMENSION_MISMATCH",
            "Embedding service dimension does not match the database schema",
            503,
        )

    # 1. Resolve workspace documents and query intent
    indexed_docs = list(
        db.scalars(
            select(Document).where(
                Document.workspace_id == workspace.id,
                Document.indexing_status == "INDEXED",
            )
        ).all()
    )
    if intent is None:
        intent = understand_query(query, indexed_docs)

    target_docs = [
        d for d in indexed_docs
        if any(m.document_id == d.id for m in intent.target_documents)
    ]
    target_doc = target_docs[0] if target_docs else None
    target_doc_ids = [d.id for d in target_docs]

    # 2. Check for explicit page-range or slide-range intent
    page_constraint = intent.page_slide_constraint
    if page_constraint is not None:
        start_page, end_page = page_constraint.start, page_constraint.end
        page_stmt = (
            select(
                DocumentChunk,
                Document.original_filename,
                ContentUnit.locator,
                ContentUnit.extraction_method,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .outerjoin(ContentUnit, ContentUnit.id == DocumentChunk.content_unit_id)
            .where(
                Document.workspace_id == workspace.id,
                Document.indexing_status == "INDEXED",
                DocumentChunk.embedding_model == provider.model_name,
                or_(
                    and_(
                        DocumentChunk.page_start <= end_page,
                        DocumentChunk.page_end >= start_page,
                    ),
                    DocumentChunk.page_number.between(start_page, end_page),
                ),
            )
        )
        if target_doc:
            page_stmt = page_stmt.where(DocumentChunk.document_id == target_doc.id)
        elif target_doc_ids:
            page_stmt = page_stmt.where(DocumentChunk.document_id.in_(target_doc_ids))

        page_rows = db.execute(
            page_stmt.order_by(Document.id, DocumentChunk.chunk_index).limit(top_k * 2)
        ).all()

        if page_rows:
            kw_set = {
                w.casefold() for w in re.findall(r"\b[A-Za-z0-9_-]{3,}\b", query)
                if w.casefold() not in {
                    "what", "when", "where", "which", "this", "that", "from", "with",
                    "about", "have", "more", "most", "some", "tell", "page", "pages",
                    "slide", "slides", "first", "give", "explanation", "summary",
                }
            }
            scored_rows = []
            for idx, (chunk, filename, locator, extraction_method) in enumerate(page_rows):
                kw_count = sum(1 for kw in kw_set if kw in chunk.text.casefold()) if kw_set else 0
                sim = max(0.70, min(0.98, 0.96 - (0.01 * idx) + (0.02 * kw_count)))
                scored_rows.append((kw_count, sim, chunk, filename, locator, extraction_method))

            if kw_set and any(item[0] > 0 for item in scored_rows):
                scored_rows.sort(key=lambda x: (x[0], x[1]), reverse=True)

            selected_rows = scored_rows[:top_k]
            return [
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    filename=filename,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    similarity=sim,
                    locator=locator,
                    extraction_method=extraction_method,
                )
                for _, sim, chunk, filename, locator, extraction_method in selected_rows
            ]

    # 3. Check for broad overview/summary intent (excluding focused topic summaries)
    if intent.task == "DOCUMENT_OVERVIEW" or (OVERVIEW_PATTERN.search(query) and intent.task != "TOPIC_SUMMARY"):
        overview_filter = [DocumentChunk.document_id.in_(target_doc_ids)] if target_doc_ids else []
        all_chunks = db.execute(
            select(
                DocumentChunk,
                Document.original_filename,
                ContentUnit.locator,
                ContentUnit.extraction_method,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .outerjoin(ContentUnit, ContentUnit.id == DocumentChunk.content_unit_id)
            .where(
                Document.workspace_id == workspace.id,
                Document.indexing_status == "INDEXED",
                DocumentChunk.embedding_model == provider.model_name,
                *overview_filter,
            )
            .order_by(Document.id, DocumentChunk.chunk_index)
        ).all()

        if all_chunks:
            if len(all_chunks) <= top_k:
                sampled = all_chunks
            else:
                step = len(all_chunks) / top_k
                indices = []
                seen_idx = set()
                for i in range(top_k):
                    idx = min(int(i * step), len(all_chunks) - 1)
                    if idx not in seen_idx:
                        seen_idx.add(idx)
                        indices.append(idx)
                sampled = [all_chunks[i] for i in indices]

            return [
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    filename=filename,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    similarity=max(0.70, 0.90 - (0.01 * idx)),
                    locator=locator,
                    extraction_method=extraction_method,
                )
                for idx, (chunk, filename, locator, extraction_method) in enumerate(sampled)
            ]

    # 4. Standard semantic vector search with keyword boost & document prioritization
    search_q = intent.search_query if (intent and intent.search_query) else query
    try:
        query_vector = validate_and_normalize(
            provider.embed_query(search_q), EMBEDDING_DIMENSION
        )
    except EmbeddingProviderError as exc:
        code = (
            "EMBEDDING_DIMENSION_MISMATCH"
            if isinstance(exc, EmbeddingDimensionError)
            else "EMBEDDING_PROVIDER_ERROR"
        )
        raise RetrievalError(code, "Search embedding could not be generated", 503) from exc

    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    candidate_limit = min(
        100, max(top_k, top_k * settings.RETRIEVAL_CANDIDATE_MULTIPLIER)
    )

    query_stmt = (
        select(
            DocumentChunk,
            Document.original_filename,
            ContentUnit.locator,
            ContentUnit.extraction_method,
            distance.label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .outerjoin(ContentUnit, ContentUnit.id == DocumentChunk.content_unit_id)
        .where(
            Document.workspace_id == workspace.id,
            Document.indexing_status == "INDEXED",
            DocumentChunk.embedding_model == provider.model_name,
        )
    )

    if target_doc_ids:
        query_stmt = query_stmt.where(DocumentChunk.document_id.in_(target_doc_ids)).order_by(
            distance,
            Document.id,
            DocumentChunk.chunk_index,
        )
    else:
        query_stmt = query_stmt.order_by(distance, Document.id, DocumentChunk.chunk_index)

    rows = db.execute(query_stmt.limit(candidate_limit)).all()

    # Extract non-stopword query keywords for lexical boosting
    keywords = [
        w.casefold()
        for w in re.findall(r"\b[A-Za-z0-9_-]{3,}\b", query)
        if w.casefold()
        not in {
            "what", "when", "where", "which", "this", "that", "from",
            "with", "about", "have", "more", "most", "some", "tell",
        }
    ]

    candidates = []
    for chunk, filename, locator, extraction_method, cosine_distance in rows:
        base_sim = max(-1.0, min(1.0, 1.0 - float(cosine_distance)))
        kw_matches = sum(1 for kw in keywords if kw in chunk.text.casefold())
        boost = min(0.10, kw_matches * 0.03)
        final_sim = min(1.0, base_sim + boost)
        candidates.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                filename=filename,
                page_number=chunk.page_number,
                text=chunk.text,
                similarity=final_sim,
                locator=locator,
                extraction_method=extraction_method,
            )
        )
    return _diversify_candidates(candidates, top_k, priority_doc_ids=target_doc_ids)
