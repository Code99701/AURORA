from dataclasses import dataclass
from collections import defaultdict, deque

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import EmbeddingDimensionError, EmbeddingProvider, EmbeddingProviderError
from app.embeddings.base import validate_and_normalize
from app.core.config import settings
from app.models.content_unit import ContentUnit
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.workspace import Workspace


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
    candidates: list[RetrievedChunk], top_k: int
) -> list[RetrievedChunk]:
    """Deduplicate within a document, then round-robin documents by best rank."""
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


def has_research_ready_sources(db: Session, workspace: Workspace) -> bool:
    ready_chunk = db.scalar(
        select(DocumentChunk.id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.workspace_id == workspace.id,
            Document.indexing_status == "INDEXED",
        )
        .limit(1)
    )
    return ready_chunk is not None


def search_workspace(
    db: Session,
    workspace: Workspace,
    query: str,
    top_k: int,
    provider: EmbeddingProvider,
) -> list[RetrievedChunk]:
    if not has_research_ready_sources(db, workspace):
        raise RetrievalError(
            "NO_RESEARCH_READY_SOURCES",
            "Process and index a workspace document before asking a grounded question",
            409,
        )
    if provider.dimension != EMBEDDING_DIMENSION:
        raise RetrievalError(
            "EMBEDDING_DIMENSION_MISMATCH",
            "Embedding service dimension does not match the database schema",
            503,
        )
    try:
        query_vector = validate_and_normalize(
            provider.embed_query(query), EMBEDDING_DIMENSION
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
    rows = db.execute(
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
        )
        .order_by(distance, Document.id, DocumentChunk.chunk_index)
        .limit(candidate_limit)
    ).all()
    candidates = [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            page_number=chunk.page_number,
            text=chunk.text,
            similarity=max(-1.0, min(1.0, 1.0 - float(cosine_distance))),
            locator=locator,
            extraction_method=extraction_method,
        )
        for chunk, filename, locator, extraction_method, cosine_distance in rows
    ]
    return _diversify_candidates(candidates, top_k)
