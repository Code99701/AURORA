import hashlib
import json
import logging
from dataclasses import dataclass
from time import perf_counter
from datetime import datetime, timezone

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
from app.rag.chunking import TextChunk, chunk_text


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


def _fingerprint(
    sources: list[IndexableSource],
    provider: EmbeddingProvider,
    ingestion_version: int | None,
) -> str:
    digest = hashlib.sha256()
    digest.update(
        (
            f"v3|ingestion:{ingestion_version or 'legacy'}|"
            f"{settings.CHUNK_SIZE_CHARACTERS}|{settings.CHUNK_OVERLAP_CHARACTERS}|"
            f"{provider.provider_name}|{provider.model_name}|{provider.dimension}"
        ).encode()
    )
    for source in sources:
        digest.update(f"|{source.ordinal}|{source.extraction_method}|".encode())
        digest.update(
            json.dumps(source.locator, sort_keys=True, separators=(",", ":")).encode()
        )
        digest.update(source.text.encode("utf-8"))
    return digest.hexdigest()


def _set_failed(db: Session, document: Document, code: str) -> None:
    db.rollback()
    try:
        document.indexing_status = "FAILED"
        document.indexing_error = code
        document.indexed_at = None
        summary = dict(document.processing_summary or {})
        summary["indexing"] = {"outcome": "FAILED", "failure_code": code}
        document.processing_summary = summary
        db.commit()
        db.refresh(document)
        logger.warning(
            "Document indexing failed",
            extra={
                "document_id": str(document.id),
                "failure_code": code,
            },
        )
    except SQLAlchemyError:
        db.rollback()
        logger.error("Unable to persist FAILED document indexing state")


def index_document(
    db: Session, document: Document, provider: EmbeddingProvider
) -> Document:
    started_at = perf_counter()
    if document.status not in {"PROCESSED", "PARTIALLY_PROCESSED"}:
        raise DocumentIndexingError(
            "DOCUMENT_NOT_PROCESSED",
            "Document must be processed before it can be indexed",
            409,
        )
    if provider.dimension != EMBEDDING_DIMENSION:
        raise DocumentIndexingError(
            "EMBEDDING_DIMENSION_MISMATCH",
            "Embedding service dimension does not match the database schema",
            503,
        )

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
    sources: list[IndexableSource]
    if active_run is not None:
        units = list(
            db.scalars(
                select(ContentUnit)
                .where(ContentUnit.ingestion_run_id == active_run.id)
                .order_by(ContentUnit.ordinal)
            ).all()
        )
        sources = []
        for unit in units:
            if unit.status != "USABLE" or not unit.text.strip():
                continue
            page = pages_by_unit_id.get(unit.id)
            located_page = unit.locator.get("page")
            page_number = (
                int(located_page)
                if isinstance(located_page, int) and located_page > 0
                else page.page_number if page is not None else None
            )
            sources.append(
                IndexableSource(
                    text=unit.text,
                    ordinal=unit.ordinal,
                    locator=unit.locator,
                    extraction_method=unit.extraction_method,
                    content_unit=unit,
                    extracted_page=page,
                    page_number=page_number,
                )
            )
    else:
        sources = [
            IndexableSource(
                text=page.text,
                ordinal=page.page_number - 1,
                locator={"v": 1, "type": "pdf_page", "page": page.page_number},
                extraction_method="NATIVE_LEGACY",
                content_unit=None,
                extracted_page=page,
                page_number=page.page_number,
            )
            for page in pages
            if page.text.strip()
        ]
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

    drafts: list[tuple[IndexableSource, TextChunk, int]] = []
    global_index = 0
    for source in sources:
        for chunk in chunk_text(
            source.text,
            settings.CHUNK_SIZE_CHARACTERS,
            settings.CHUNK_OVERLAP_CHARACTERS,
        ):
            drafts.append((source, chunk, global_index))
            global_index += 1
    if not drafts:
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

    try:
        vectors = provider.embed_documents([chunk.text for _, chunk, _ in drafts])
        if len(vectors) != len(drafts):
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

    try:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.add_all(
            DocumentChunk(
                document_id=document.id,
                extracted_page_id=(
                    source.extracted_page.id if source.extracted_page is not None else None
                ),
                content_unit_id=(
                    source.content_unit.id if source.content_unit is not None else None
                ),
                page_number=source.page_number,
                chunk_index=global_chunk_index,
                page_chunk_index=chunk.page_chunk_index,
                text=chunk.text,
                character_count=chunk.character_count,
                approximate_token_count=chunk.approximate_token_count,
                embedding=vector,
                embedding_model=provider.model_name,
            )
            for (source, chunk, global_chunk_index), vector in zip(
                drafts, vectors, strict=True
            )
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
            "chunk_count": len(drafts),
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
                "chunk_count": len(drafts),
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
