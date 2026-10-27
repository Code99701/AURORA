import hashlib
import json
import logging
from dataclasses import dataclass
import time
from time import perf_counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.embeddings import EmbeddingDimensionError, EmbeddingProvider, EmbeddingProviderError
from app.embeddings.base import validate_and_normalize
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.extracted_page import ExtractedPage
from app.models.content_unit import ContentUnit
from app.models.ingestion_run import IngestionRun
from app.rag.chunking import StructuredChunk, TextChunk, chunk_document_sources, chunk_text


logger = logging.getLogger(__name__)


class DocumentIndexingError(Exception):
    def __init__(self, code: str, public_message: str, status_code: int):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


@dataclass(frozen=True)
class IndexableSource:
    text: str
    ordinal: int
    locator: dict
    extraction_method: str
    content_unit: ContentUnit | None
    extracted_page: ExtractedPage | None
    page_number: int | None
    id: Any = None


@dataclass
class ReindexStats:
    document_id: str
    filename: str
    old_chunk_count: int
    new_chunk_count: int
    old_avg_length: float
    new_avg_length: float
    old_tiny_chunks: int
    new_tiny_chunks: int
    dry_run: bool
    status: str
    error: str | None = None


def _fingerprint(
    sources: list[IndexableSource],
    provider: EmbeddingProvider,
    ingestion_version: int | None,
) -> str:
    digest = hashlib.sha256()
    digest.update(
        (
            f"v4|ingestion:{ingestion_version or 'legacy'}|"
            f"{settings.CHUNK_SIZE_CHARACTERS}|{settings.CHUNK_OVERLAP_CHARACTERS}|"
            f"{provider.provider_name}|{provider.model_name}|{provider.dimension}"
        ).encode()
    )
    for source in sources:
        digest.update(f"|{source.ordinal}|{source.extraction_method}|".encode())
        digest.update(source.text.encode())
    return digest.hexdigest()


def _set_failed(db: Session, document: Document, code: str) -> None:
    try:
        document.indexing_status = "FAILED"
        document.indexing_error = code
        document.indexed_at = None
        db.commit()
    except SQLAlchemyError:
        db.rollback()


def get_indexable_sources(db: Session, document: Document) -> list[IndexableSource]:
    """Retrieve raw indexable sources for a document from pages or content units."""
    pages = list(
        db.scalars(
            select(ExtractedPage)
            .where(ExtractedPage.document_id == document.id)
            .order_by(ExtractedPage.page_number)
        ).all()
    )
    active_run = db.scalar(
        select(IngestionRun).where(
            IngestionRun.document_id == document.id,
            IngestionRun.status == "ACTIVE",
        )
    )
    pages_by_unit_id = {
        page.content_unit_id: page for page in pages if page.content_unit_id is not None
    }
    if active_run is not None:
        units = list(
            db.scalars(
                select(ContentUnit)
                .where(ContentUnit.ingestion_run_id == active_run.id)
                .order_by(ContentUnit.ordinal)
            ).all()
        )
        sources: list[IndexableSource] = []
        for unit in units:
            if unit.status != "USABLE" or not unit.text.strip():
                continue
            page = pages_by_unit_id.get(unit.id)
            located_page = unit.locator.get("page") if unit.locator else None
            page_number = (
                int(located_page)
                if isinstance(located_page, int) and located_page > 0
                else page.page_number if page is not None else None
            )
            sources.append(
                IndexableSource(
                    text=unit.text,
                    ordinal=unit.ordinal,
                    locator=unit.locator or {},
                    extraction_method=unit.extraction_method,
                    content_unit=unit,
                    extracted_page=page,
                    page_number=page_number,
                    id=unit.id,
                )
            )
        return sources

    return [
        IndexableSource(
            text=page.text,
            ordinal=page.page_number - 1,
            locator={"v": 1, "type": "pdf_page", "page": page.page_number},
            extraction_method="NATIVE_LEGACY",
            content_unit=None,
            extracted_page=page,
            page_number=page.page_number,
            id=page.id,
        )
        for page in pages
        if page.text.strip()
    ]


def reset_stuck_indexing_documents(
    db: Session,
    timeout_minutes: int = 15,
) -> list[Document]:
    """Recover documents stuck in INDEXING longer than timeout_minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    stuck_docs = list(
        db.scalars(
            select(Document).where(
                Document.indexing_status == "INDEXING",
                Document.updated_at < cutoff,
            )
        ).all()
    )
    recovered = []
    for doc in stuck_docs:
        doc.indexing_status = "FAILED"
        doc.indexing_error = "INDEXING_TIMEOUT"
        doc.updated_at = datetime.now(timezone.utc)
        recovered.append(doc)
    if recovered:
        try:
            db.commit()
            for doc in recovered:
                db.refresh(doc)
            logger.warning(
                "Reset %d documents stuck in INDEXING to FAILED",
                len(recovered),
            )
        except SQLAlchemyError:
            db.rollback()
    return recovered


def index_document(
    db: Session,
    document: Document,
    provider: EmbeddingProvider,
) -> Document:
    """Structure-aware indexing pipeline with slide merging and contextual prefixes."""
    started_at = perf_counter()
    if document.status not in {"PROCESSED", "PARTIALLY_PROCESSED"}:
        raise DocumentIndexingError(
            "DOCUMENT_NOT_PROCESSED", "Document must be processed before it can be indexed", 409
        )
    if provider.dimension != EMBEDDING_DIMENSION:
        _set_failed(db, document, "EMBEDDING_DIMENSION_MISMATCH")
        raise DocumentIndexingError(
            "EMBEDDING_DIMENSION_MISMATCH",
            "Embedding service dimension does not match the database schema",
            503,
        )


    sources = get_indexable_sources(db, document)
    active_run = db.scalar(
        select(IngestionRun).where(
            IngestionRun.document_id == document.id,
            IngestionRun.status == "ACTIVE",
        )
    )
    fingerprint = _fingerprint(
        sources, provider, active_run.version if active_run is not None else None
    )
    existing_count = db.scalar(
        select(func.count()).select_from(DocumentChunk).where(
            DocumentChunk.document_id == document.id
        )
    )
    if (
        document.indexing_status == "INDEXED"
        and document.indexing_fingerprint == fingerprint
        and existing_count
    ):
        return document

    # Structure-aware chunking
    structured_chunks = chunk_document_sources(
        sources=sources,
        document_filename=document.original_filename,
        target_chunk_size=settings.CHUNK_SIZE_CHARACTERS,
        overlap=settings.CHUNK_OVERLAP_CHARACTERS,
    )
    if not structured_chunks:
        _set_failed(db, document, "NO_INDEXABLE_TEXT")
        raise DocumentIndexingError(
            "NO_INDEXABLE_TEXT", "Document contains no text that can be indexed", 422
        )

    try:
        document.indexing_status = "INDEXING"
        document.indexing_error = None
        document.indexed_at = None
        db.commit()
        db.refresh(document)
    except SQLAlchemyError as exc:
        _set_failed(db, document, "INDEXING_STATE_ERROR")
        raise DocumentIndexingError(
            "INDEXING_STATE_ERROR", "Unable to start document indexing", 500
        ) from exc

    # Embed contextual representation
    try:
        vectors = provider.embed_documents([chunk.embedded_text for chunk in structured_chunks])
        if len(vectors) != len(structured_chunks):
            raise EmbeddingDimensionError("Embedding result count mismatch")
        vectors = [validate_and_normalize(vector, EMBEDDING_DIMENSION) for vector in vectors]
    except EmbeddingProviderError as exc:
        code = (
            "EMBEDDING_DIMENSION_MISMATCH"
            if isinstance(exc, EmbeddingDimensionError)
            else "EMBEDDING_PROVIDER_ERROR"
        )
        _set_failed(db, document, code)
        raise DocumentIndexingError(
            code, "Document embeddings could not be generated", 503
        ) from exc

    # Atomic swap: commit all chunks and indexing state in one transaction
    try:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.add_all(
            DocumentChunk(
                document_id=document.id,
                extracted_page_id=chunk.extracted_page_id,
                content_unit_id=chunk.content_unit_id,
                page_number=chunk.page_number,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                context_prefix=chunk.context_prefix,
                tsv=func.to_tsvector("simple", chunk.embedded_text),
                chunk_index=chunk.chunk_index,
                page_chunk_index=chunk.page_chunk_index,
                text=chunk.text,
                character_count=chunk.character_count,
                approximate_token_count=chunk.approximate_token_count,
                embedding=vector,
                embedding_model=provider.model_name,
            )
            for chunk, vector in zip(structured_chunks, vectors, strict=True)
        )
        document.indexing_status = "INDEXED"
        document.indexing_error = None
        document.indexed_at = datetime.now(timezone.utc)
        document.embedding_model = provider.model_name
        document.embedding_dimension = provider.dimension
        document.indexing_fingerprint = fingerprint
        duration_ms = max(0, round((perf_counter() - started_at) * 1000))
        summary = dict(document.processing_summary or {})
        summary["indexing"] = {
            "outcome": "COMPLETE",
            "chunk_count": len(structured_chunks),
            "embedding_provider": provider.provider_name,
            "embedding_model": provider.model_name,
            "duration_ms": duration_ms,
        }
        document.processing_summary = summary
        db.commit()
        db.refresh(document)
        logger.info(
            "Document index activated",
            extra={
                "document_id": str(document.id),
                "chunk_count": len(structured_chunks),
                "embedding_provider": provider.provider_name,
                "embedding_model": provider.model_name,
                "duration_ms": duration_ms,
            },
        )
        return document
    except SQLAlchemyError as exc:
        _set_failed(db, document, "CHUNK_PERSISTENCE_ERROR")
        raise DocumentIndexingError(
            "CHUNK_PERSISTENCE_ERROR", "Document index could not be saved", 500
        ) from exc


def reindex_document(
    db: Session,
    document: Document,
    provider: EmbeddingProvider,
    dry_run: bool = True,
    batch_size: int = 20,
) -> ReindexStats:
    """Re-index a document with atomic swap and dry-run preview.

    Guarantees:
    - In dry-run mode, calculates chunk differences without touching DB.
    - Never deletes old chunks until all new chunks are fully embedded.
    - A failed or 429 re-index rolls back cleanly, leaving old chunks intact.
    """
    existing_chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        ).all()
    )
    old_count = len(existing_chunks)
    old_avg = (sum(c.character_count for c in existing_chunks) / old_count) if old_count else 0.0
    old_tiny = sum(1 for c in existing_chunks if c.character_count < 80)

    sources = get_indexable_sources(db, document)
    candidate_chunks = chunk_document_sources(
        sources=sources,
        document_filename=document.original_filename,
        target_chunk_size=settings.CHUNK_SIZE_CHARACTERS,
        overlap=settings.CHUNK_OVERLAP_CHARACTERS,
    )
    new_count = len(candidate_chunks)
    new_avg = (sum(c.character_count for c in candidate_chunks) / new_count) if new_count else 0.0
    new_tiny = sum(1 for c in candidate_chunks if c.character_count < 80)

    stats = ReindexStats(
        document_id=str(document.id),
        filename=document.original_filename,
        old_chunk_count=old_count,
        new_chunk_count=new_count,
        old_avg_length=round(old_avg, 1),
        new_avg_length=round(new_avg, 1),
        old_tiny_chunks=old_tiny,
        new_tiny_chunks=new_tiny,
        dry_run=dry_run,
        status="DRY_RUN" if dry_run else "PENDING",
    )

    if dry_run or not candidate_chunks:
        return stats

    # Non-dry-run execution: embed candidate chunks in throttled batches
    try:
        all_vectors: list[list[float]] = []
        for i in range(0, len(candidate_chunks), batch_size):
            batch = candidate_chunks[i : i + batch_size]
            batch_texts = [c.embedded_text for c in batch]
            logger.info(
                "Embedding batch %d-%d of %d for %s",
                i + 1,
                min(i + batch_size, len(candidate_chunks)),
                len(candidate_chunks),
                document.original_filename,
            )
            batch_vectors = provider.embed_documents(batch_texts)
            for v in batch_vectors:
                all_vectors.append(validate_and_normalize(v, EMBEDDING_DIMENSION))
            if i + batch_size < len(candidate_chunks):
                time.sleep(1.0)

        # Atomic swap in a single transaction:
        # Delete old chunks only after all new embeddings are ready
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.add_all(
            DocumentChunk(
                document_id=document.id,
                extracted_page_id=chunk.extracted_page_id,
                content_unit_id=chunk.content_unit_id,
                page_number=chunk.page_number,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                context_prefix=chunk.context_prefix,
                tsv=func.to_tsvector("simple", chunk.embedded_text),
                chunk_index=chunk.chunk_index,
                page_chunk_index=chunk.page_chunk_index,
                text=chunk.text,
                character_count=chunk.character_count,
                approximate_token_count=chunk.approximate_token_count,
                embedding=vector,
                embedding_model=provider.model_name,
            )
            for chunk, vector in zip(candidate_chunks, all_vectors, strict=True)
        )
        document.indexing_status = "INDEXED"
        document.indexing_error = None
        document.indexed_at = datetime.now(timezone.utc)
        document.embedding_model = provider.model_name
        document.embedding_dimension = provider.dimension
        db.commit()
        db.refresh(document)
        stats.status = "SUCCESS"
        return stats
    except Exception as exc:
        db.rollback()
        stats.status = "FAILED"
        stats.error = str(exc)
        logger.error(
            "Re-indexing failed for document %s: %s (old chunks preserved intact)",
            document.id,
            exc,
        )
        return stats
