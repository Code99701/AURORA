import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ingestion import (
    AdapterError,
    AdapterRegistry,
    CanonicalDocument,
    ExtractionContext,
    ExtractionLimits,
    get_adapter_registry,
)
from app.models.content_unit import ContentUnit
from app.models.document import Document
from app.models.ingestion_run import IngestionRun
from app.models.extracted_page import ExtractedPage
from app.ocr.base import OCRProvider
from app.storage.base import FileStorage, StorageError


logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    def __init__(self, code: str, public_message: str, status_code: int):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


@dataclass(frozen=True)
class PreviousDocumentState:
    valid: bool
    status: str
    processing_stage: str | None
    processing_error: str | None
    page_count: int | None
    processed_at: datetime | None
    processing_summary: dict


def _limits() -> ExtractionLimits:
    return ExtractionLimits(
        maximum_file_bytes=settings.DOCUMENT_MAX_SIZE_BYTES,
        maximum_pages=settings.PDF_MAX_PAGES,
        render_dpi=settings.PDF_RENDER_DPI,
        maximum_rendered_pixels_per_page=settings.PDF_MAX_RENDERED_PIXELS_PER_PAGE,
        maximum_total_rendered_pixels=settings.PDF_MAX_TOTAL_RENDERED_PIXELS,
        maximum_ocr_pages=settings.OCR_MAX_PAGES,
        ocr_timeout_seconds_per_page=settings.OCR_TIMEOUT_SECONDS_PER_PAGE,
        native_minimum_characters=settings.NATIVE_TEXT_MIN_CHARACTERS,
        ocr_minimum_characters=settings.OCR_TEXT_MIN_CHARACTERS,
        minimum_printable_ratio=settings.EXTRACTION_MIN_PRINTABLE_RATIO,
        minimum_ocr_confidence=settings.OCR_MIN_CONFIDENCE,
        maximum_extracted_characters=settings.EXTRACTION_MAX_CHARACTERS,
        maximum_units=settings.INGESTION_MAX_UNITS,
        maximum_rows=settings.TABULAR_MAX_ROWS,
        maximum_columns=settings.TABULAR_MAX_COLUMNS,
        maximum_table_cells=settings.TABULAR_MAX_CELLS,
        maximum_field_characters=settings.TABULAR_MAX_FIELD_CHARACTERS,
        maximum_archive_entries=settings.OOXML_MAX_ARCHIVE_ENTRIES,
        maximum_archive_uncompressed_bytes=settings.OOXML_MAX_UNCOMPRESSED_BYTES,
        maximum_paragraphs=settings.DOCX_MAX_PARAGRAPHS,
        maximum_slides=settings.PPTX_MAX_SLIDES,
        maximum_sheets=settings.XLSX_MAX_SHEETS,
        tabular_rows_per_unit=settings.TABULAR_ROWS_PER_UNIT,
    )


def _snapshot(db: Session, document: Document) -> PreviousDocumentState:
    page_count = db.scalar(
        select(func.count()).select_from(ExtractedPage).where(
            ExtractedPage.document_id == document.id
        )
    ) or 0
    canonical_unit_count = db.scalar(
        select(func.count())
        .select_from(ContentUnit)
        .join(IngestionRun, IngestionRun.id == ContentUnit.ingestion_run_id)
        .where(
            ContentUnit.document_id == document.id,
            ContentUnit.status == "USABLE",
            IngestionRun.status == "ACTIVE",
        )
    ) or 0
    return PreviousDocumentState(
        valid=(
            document.status in {"PROCESSED", "PARTIALLY_PROCESSED"}
            and (page_count > 0 or canonical_unit_count > 0)
        ),
        status=document.status,
        processing_stage=document.processing_stage,
        processing_error=document.processing_error,
        page_count=document.page_count,
        processed_at=document.processed_at,
        processing_summary=dict(document.processing_summary or {}),
    )


def _next_version(db: Session, document: Document) -> int:
    current = db.scalar(
        select(func.max(IngestionRun.version)).where(
            IngestionRun.document_id == document.id
        )
    )
    return (current or 0) + 1


def _record_failure(
    db: Session,
    document_id,
    run_id,
    previous: PreviousDocumentState,
    code: str,
    page_count: int | None,
    failure_stage: str = "EXTRACTION",
    diagnostics: dict | None = None,
) -> None:
    db.rollback()
    try:
        document = db.get(Document, document_id)
        run = db.get(IngestionRun, run_id)
        if run is not None:
            completed_at = datetime.now(timezone.utc)
            run.status = "FAILED"
            run.failure_code = code
            run.failure_stage = failure_stage
            run.outcome = "FAILED"
            run.page_count = page_count
            run.diagnostics = diagnostics or {}
            run.completed_at = completed_at
            run.duration_ms = max(
                0, int((completed_at - run.started_at).total_seconds() * 1000)
            )
        if document is not None:
            if previous.valid:
                document.status = previous.status
                document.page_count = previous.page_count
                document.processed_at = previous.processed_at
                document.processing_summary = previous.processing_summary
            else:
                document.status = "FAILED"
                document.page_count = page_count
                document.processed_at = None
                document.processing_summary = diagnostics or {}
            document.processing_stage = "FAILED"
            document.processing_error = code
        db.commit()
        logger.warning(
            "Document ingestion failed",
            extra={
                "document_id": str(document_id),
                "ingestion_run_id": str(run_id),
                "failure_code": code,
                "failure_stage": failure_stage,
                "page_count": page_count,
                "duration_ms": run.duration_ms if run is not None else None,
            },
        )
    except SQLAlchemyError:
        db.rollback()
        logger.error("Unable to persist FAILED document ingestion state")


def _stage_units(
    db: Session,
    document: Document,
    run: IngestionRun,
    canonical: CanonicalDocument,
) -> list[ContentUnit]:
    units = [
        ContentUnit(
            document_id=document.id,
            ingestion_run_id=run.id,
            ordinal=draft.ordinal,
            kind=draft.kind,
            text=draft.text,
            character_count=draft.character_count,
            language=draft.language,
            locator_version=int(draft.locator.get("v", 1)),
            locator=draft.locator,
            extraction_method=draft.extraction_method,
            content_type=draft.content_type,
            status=draft.status,
            issue_code=draft.issue_code,
            confidence=draft.confidence,
            unit_metadata=draft.metadata,
        )
        for draft in canonical.units
    ]
    units_by_ordinal = {unit.ordinal: unit for unit in units}
    for unit, draft in zip(units, canonical.units, strict=True):
        if draft.parent_ordinal is not None:
            unit.parent = units_by_ordinal.get(draft.parent_ordinal)
    db.add_all(units)
    run.status = "STAGED"
    run.outcome = canonical.outcome
    run.page_count = canonical.page_count
    run.unit_count = len(units)
    run.diagnostics = canonical.diagnostics
    document.processing_stage = "PERSISTING"
    db.commit()
    for unit in units:
        db.refresh(unit)
    return units


def _activate(
    db: Session,
    document: Document,
    run: IngestionRun,
    units: list[ContentUnit],
    canonical: CanonicalDocument,
) -> Document:
    now = datetime.now(timezone.utc)
    db.execute(
        update(IngestionRun)
        .where(
            IngestionRun.document_id == document.id,
            IngestionRun.status == "ACTIVE",
            IngestionRun.id != run.id,
        )
        .values(status="SUPERSEDED")
    )
    # Release the partial unique ACTIVE slot before activating the staged run.
    db.flush()

    # The old compatible page/index view remains live until this transaction.
    # Any failure rolls the delete and replacement back together.
    db.execute(delete(ExtractedPage).where(ExtractedPage.document_id == document.id))
    db.flush()
    for unit in units:
        page_number = unit.locator.get("page")
        if unit.kind == "PAGE" and isinstance(page_number, int) and page_number > 0:
            db.add(
                ExtractedPage(
                    document_id=document.id,
                    content_unit_id=unit.id,
                    page_number=page_number,
                    text=unit.text,
                    character_count=unit.character_count,
                )
            )

    run.status = "ACTIVE"
    run.completed_at = now
    run.duration_ms = max(0, int((now - run.started_at).total_seconds() * 1000))
    run.failure_code = None
    run.failure_stage = None
    run.outcome = canonical.outcome
    run.diagnostics = canonical.diagnostics
    document.status = (
        "PARTIALLY_PROCESSED" if canonical.outcome == "PARTIAL" else "PROCESSED"
    )
    document.processing_stage = canonical.outcome
    document.processing_error = None
    document.processing_summary = canonical.diagnostics
    document.page_count = canonical.page_count
    document.processed_at = now
    document.indexing_status = "NOT_INDEXED"
    document.indexing_error = None
    document.indexed_at = None
    document.embedding_model = None
    document.embedding_dimension = None
    document.indexing_fingerprint = None
    db.commit()
    db.refresh(document)
    logger.info(
        "Document ingestion activated",
        extra={
            "document_id": str(document.id),
            "ingestion_run_id": str(run.id),
            "ingestion_outcome": canonical.outcome,
            "unit_count": len(units),
            "duration_ms": run.duration_ms,
        },
    )
    return document


def process_document(
    db: Session,
    storage: FileStorage,
    document: Document,
    ocr_provider: OCRProvider,
    registry: AdapterRegistry | None = None,
) -> Document:
    """Stage canonical content units and atomically activate the new ingestion run."""
    registry = registry or get_adapter_registry()
    locked_document = db.scalar(
        select(Document).where(Document.id == document.id).with_for_update()
    )
    if locked_document is None:
        raise DocumentProcessingError(
            "DOCUMENT_NOT_FOUND", "Document was not found", 404
        )
    document = locked_document
    if document.status == "PROCESSING":
        db.rollback()
        raise DocumentProcessingError(
            "DOCUMENT_PROCESSING_IN_PROGRESS",
            "Document processing is already in progress",
            409,
        )
    previous = _snapshot(db, document)
    run = IngestionRun(
        document_id=document.id,
        version=_next_version(db, document),
        adapter_id="pending",
        adapter_version="pending",
        source_format="pending",
        status="PROCESSING",
        diagnostics={},
    )
    try:
        document.status = "PROCESSING"
        document.processing_stage = "NATIVE_EXTRACTION"
        document.processing_error = None
        db.add(run)
        db.commit()
        db.refresh(run)
        db.refresh(document)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DocumentProcessingError(
            "PROCESSING_STATE_ERROR", "Unable to start document processing", 500
        ) from exc

    try:
        adapter = registry.resolve_document(
            document.content_type, document.original_filename
        )
        run.adapter_id = adapter.adapter_id
        run.adapter_version = adapter.adapter_version
        run.source_format = adapter.source_format
        document.processing_stage = "EXTRACTING"
        db.flush()
        with storage.open(document.storage_key) as source:
            canonical = adapter.extract(
                source,
                ExtractionContext(ocr_provider=ocr_provider, limits=_limits()),
            )
    except StorageError as exc:
        _record_failure(
            db,
            document.id,
            run.id,
            previous,
            "STORAGE_READ_ERROR",
            None,
            "STORAGE",
        )
        raise DocumentProcessingError(
            "STORAGE_READ_ERROR", "Stored document could not be read", 503
        ) from exc
    except AdapterError as exc:
        _record_failure(
            db,
            document.id,
            run.id,
            previous,
            exc.code,
            exc.page_count,
            exc.failure_stage,
            exc.diagnostics,
        )
        raise DocumentProcessingError(exc.code, exc.public_message, exc.status_code) from exc
    except Exception as exc:
        _record_failure(
            db,
            document.id,
            run.id,
            previous,
            "DOCUMENT_EXTRACTION_ERROR",
            None,
            "EXTRACTION",
        )
        raise DocumentProcessingError(
            "DOCUMENT_EXTRACTION_ERROR", "Document extraction failed", 422
        ) from exc

    try:
        units = _stage_units(db, document, run, canonical)
        return _activate(db, document, run, units, canonical)
    except SQLAlchemyError as exc:
        _record_failure(
            db,
            document.id,
            run.id,
            previous,
            "EXTRACTED_CONTENT_PERSISTENCE_ERROR",
            canonical.page_count,
            "PERSISTENCE",
            canonical.diagnostics,
        )
        raise DocumentProcessingError(
            "EXTRACTED_CONTENT_PERSISTENCE_ERROR",
            "Extracted content could not be activated",
            500,
        ) from exc
