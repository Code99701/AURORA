from dataclasses import dataclass, field
from typing import BinaryIO, Protocol

from app.ocr.base import OCRProvider


class AdapterError(Exception):
    def __init__(
        self,
        code: str,
        public_message: str,
        status_code: int = 422,
        page_count: int | None = None,
        failure_stage: str = "EXTRACTION",
        diagnostics: dict | None = None,
    ):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code
        self.page_count = page_count
        self.failure_stage = failure_stage
        self.diagnostics = diagnostics or {}


@dataclass(frozen=True)
class AdapterCapabilities:
    extensions: tuple[str, ...]
    media_types: tuple[str, ...]
    unit_kinds: tuple[str, ...]
    supports_partial_results: bool
    supports_native_extraction: bool
    supports_ocr_fallback: bool


@dataclass(frozen=True)
class ExtractionLimits:
    maximum_file_bytes: int
    maximum_pages: int
    render_dpi: int
    maximum_rendered_pixels_per_page: int
    maximum_total_rendered_pixels: int
    maximum_ocr_pages: int
    ocr_timeout_seconds_per_page: float
    native_minimum_characters: int
    ocr_minimum_characters: int
    minimum_printable_ratio: float
    minimum_ocr_confidence: float
    maximum_extracted_characters: int
    maximum_units: int = 10_000
    maximum_rows: int = 50_000
    maximum_columns: int = 500
    maximum_table_cells: int = 250_000
    maximum_field_characters: int = 100_000
    maximum_archive_entries: int = 10_000
    maximum_archive_uncompressed_bytes: int = 100 * 1024 * 1024
    maximum_paragraphs: int = 20_000
    maximum_slides: int = 1_000
    maximum_sheets: int = 250
    tabular_rows_per_unit: int = 50


@dataclass(frozen=True)
class ExtractionContext:
    ocr_provider: OCRProvider
    limits: ExtractionLimits


@dataclass(frozen=True)
class ContentUnitDraft:
    ordinal: int
    kind: str
    text: str
    locator: dict
    extraction_method: str
    content_type: str = "text/plain"
    status: str = "USABLE"
    issue_code: str | None = None
    parent_ordinal: int | None = None
    language: str | None = None
    confidence: float | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def character_count(self) -> int:
        return len(self.text)


@dataclass(frozen=True)
class CanonicalDocument:
    source_format: str
    adapter_id: str
    adapter_version: str
    units: tuple[ContentUnitDraft, ...]
    page_count: int | None
    warnings: tuple[str, ...] = ()
    outcome: str = "COMPLETE"
    diagnostics: dict = field(default_factory=dict)


class FormatAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    source_format: str
    capabilities: AdapterCapabilities

    def extract(
        self, source: BinaryIO, context: ExtractionContext
    ) -> CanonicalDocument: ...
