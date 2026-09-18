from collections import Counter
from typing import BinaryIO

from app.ingestion.base import (
    AdapterError,
    CanonicalDocument,
    ContentUnitDraft,
    ExtractionLimits,
)
from app.processing.text import clean_extracted_text


def read_bounded(source: BinaryIO, maximum_bytes: int) -> bytes:
    try:
        source.seek(0)
        data = source.read(maximum_bytes + 1)
    except (OSError, ValueError, AttributeError) as exc:
        raise AdapterError(
            "STORAGE_READ_ERROR",
            "Stored document could not be read",
            503,
            failure_stage="STORAGE",
        ) from exc
    if not data or len(data) > maximum_bytes:
        raise AdapterError(
            "DOCUMENT_SIZE_LIMIT",
            "The stored document exceeds the configured processing limit",
            422,
            failure_stage="VALIDATION",
        )
    return data


def decode_utf8(data: bytes) -> tuple[str, bool]:
    try:
        return data.decode("utf-8-sig"), False
    except UnicodeDecodeError:
        return data.decode("utf-8-sig", errors="replace"), True


def normalized_text(value: str | None) -> str:
    return clean_extracted_text(value or "")


def finalize_document(
    *,
    source_format: str,
    adapter_id: str,
    adapter_version: str,
    units: list[ContentUnitDraft],
    limits: ExtractionLimits,
    warnings: list[str] | None = None,
    diagnostics: dict | None = None,
    page_count: int | None = None,
) -> CanonicalDocument:
    if len(units) > limits.maximum_units:
        raise AdapterError(
            "CONTENT_UNIT_LIMIT",
            "Document produced more content units than the configured limit",
            422,
            page_count,
            failure_stage="CANONICALIZATION",
        )
    total_characters = sum(unit.character_count for unit in units)
    if total_characters > limits.maximum_extracted_characters:
        raise AdapterError(
            "EXTRACTED_CONTENT_LIMIT",
            "Extracted text exceeded the configured content limit",
            422,
            page_count,
            failure_stage="NORMALIZATION",
        )
    usable = sum(unit.status == "USABLE" and bool(unit.text.strip()) for unit in units)
    skipped = sum(unit.status == "SKIPPED" for unit in units)
    failed = sum(unit.status == "FAILED" for unit in units)
    issue_counts = Counter(
        unit.issue_code for unit in units if unit.issue_code is not None
    )
    method_counts = Counter(unit.extraction_method for unit in units)
    safe_diagnostics = {
        "unit_count": len(units),
        "usable_unit_count": usable,
        "skipped_unit_count": skipped,
        "failed_unit_count": failed,
        "character_count": total_characters,
        "method_counts": dict(sorted(method_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        **(diagnostics or {}),
    }
    if not usable:
        raise AdapterError(
            "NO_EXTRACTABLE_TEXT",
            "Document contains no extractable text",
            422,
            page_count,
            diagnostics=safe_diagnostics,
        )
    outcome = "PARTIAL" if failed else "COMPLETE"
    return CanonicalDocument(
        source_format=source_format,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        units=tuple(units),
        page_count=page_count,
        warnings=tuple(warnings or ()),
        outcome=outcome,
        diagnostics=safe_diagnostics,
    )

