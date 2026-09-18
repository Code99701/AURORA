import re
from collections import Counter
from io import BytesIO
from typing import BinaryIO

import pypdfium2 as pdfium
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingestion.base import (
    AdapterCapabilities,
    AdapterError,
    CanonicalDocument,
    ContentUnitDraft,
    ExtractionContext,
)
from app.ocr.base import OCRError
from app.processing.text import clean_extracted_text


TEXT_OPERATOR = re.compile(rb"(?<!\S)(?:BT|Tj|TJ|Tf|ET)(?=\s|$)")
VECTOR_PAINT_OPERATOR = re.compile(
    rb"(?<!\S)(?:m|l|c|v|y|h|re|S|s|f|F|f\*|B|B\*|b|b\*)(?=\s|$)"
)


def _quality_metrics(text: str) -> dict[str, float | int]:
    if not text:
        return {
            "characters": 0,
            "alphanumeric_characters": 0,
            "printable_ratio": 0.0,
            "alphanumeric_ratio": 0.0,
            "replacement_ratio": 0.0,
            "longest_repeated_run_ratio": 0.0,
        }
    printable = sum(character.isprintable() or character.isspace() for character in text)
    alphanumeric = sum(character.isalnum() for character in text)
    replacement = text.count("\ufffd")
    longest_run = 1
    current_run = 1
    for previous, current in zip(text, text[1:]):
        current_run = current_run + 1 if current == previous else 1
        longest_run = max(longest_run, current_run)
    return {
        "characters": len(text),
        "alphanumeric_characters": alphanumeric,
        "printable_ratio": round(printable / len(text), 4),
        "alphanumeric_ratio": round(alphanumeric / len(text), 4),
        "replacement_ratio": round(replacement / len(text), 4),
        "longest_repeated_run_ratio": round(longest_run / len(text), 4),
    }


def _has_image_xobject(page) -> bool:
    try:
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") or {}
        for value in xobjects.values():
            resolved = value.get_object()
            if resolved.get("/Subtype") == "/Image":
                return True
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
    return False


def _page_signals(page) -> tuple[bool, bool, bool, bool]:
    try:
        contents = page.get_contents()
        raw = contents.get_data() if contents is not None else b""
    except Exception:
        raw = b""
    return (
        bool(raw.strip()),
        bool(TEXT_OPERATOR.search(raw)),
        bool(VECTOR_PAINT_OPERATOR.search(raw)),
        _has_image_xobject(page),
    )


def _page_geometry(page) -> dict[str, float | int | None]:
    try:
        box = page.mediabox
        return {
            "width_points": round(float(box.width), 2),
            "height_points": round(float(box.height), 2),
            "rotation_degrees": int(page.get("/Rotate", 0) or 0) % 360,
        }
    except (AttributeError, TypeError, ValueError):
        return {
            "width_points": None,
            "height_points": None,
            "rotation_degrees": None,
        }


class PDFAdapter:
    adapter_id = "aurora.pdf"
    adapter_version = "1.1"
    source_format = "pdf"
    capabilities = AdapterCapabilities(
        extensions=(".pdf",),
        media_types=("application/pdf",),
        unit_kinds=("PAGE",),
        supports_partial_results=True,
        supports_native_extraction=True,
        supports_ocr_fallback=True,
    )

    def extract(
        self, source: BinaryIO, context: ExtractionContext
    ) -> CanonicalDocument:
        limits = context.limits
        data = self._read_bounded(source, limits.maximum_file_bytes)
        reader, page_count = self._open_reader(data)
        if page_count == 0:
            raise AdapterError(
                "NO_EXTRACTABLE_TEXT", "PDF contains no readable pages", 422, 0
            )
        if page_count > limits.maximum_pages:
            raise AdapterError(
                "PDF_PAGE_LIMIT",
                "PDF exceeds the configured page limit",
                422,
                page_count,
                failure_stage="VALIDATION",
            )

        rendered_document = None
        units: list[ContentUnitDraft] = []
        warnings: list[str] = []
        issue_counts: Counter[str] = Counter()
        method_counts: Counter[str] = Counter()
        ocr_pages = 0
        total_rendered_pixels = 0
        total_characters = 0
        first_failure: tuple[str, str, int] | None = None

        try:
            for index in range(page_count):
                page_number = index + 1
                try:
                    page = reader.pages[index]
                    has_content, has_text_ops, has_vectors, has_images = _page_signals(page)
                    geometry = _page_geometry(page)
                    try:
                        native_text = clean_extracted_text(page.extract_text() or "")
                    except Exception:
                        native_text = ""
                except Exception:
                    code = "PDF_PAGE_EXTRACTION_ERROR"
                    first_failure = first_failure or (
                        code,
                        f"PDF page {page_number} could not be extracted",
                        422,
                    )
                    issue_counts[code] += 1
                    units.append(self._failed_unit(index, page_number, code, "NATIVE"))
                    continue

                native_quality = _quality_metrics(native_text)
                if self._native_is_usable(
                    native_text,
                    has_text_ops,
                    limits.native_minimum_characters,
                    limits.minimum_printable_ratio,
                ):
                    unit = ContentUnitDraft(
                        ordinal=index,
                        kind="PAGE",
                        text=native_text,
                        locator={"v": 1, "type": "pdf_page", "page": page_number},
                        extraction_method="NATIVE",
                        metadata={
                            "classification": "MIXED" if has_images else "NATIVE_TEXT",
                            "quality": native_quality,
                            "ocr_regions": [],
                            "render_dpi": None,
                            "geometry": geometry,
                        },
                    )
                elif self._is_blank(
                    native_text, has_content, has_text_ops, has_vectors, has_images
                ):
                    issue_counts["BLANK_PAGE"] += 1
                    unit = ContentUnitDraft(
                        ordinal=index,
                        kind="PAGE",
                        text="",
                        locator={"v": 1, "type": "pdf_page", "page": page_number},
                        extraction_method="BLANK",
                        status="SKIPPED",
                        issue_code="BLANK_PAGE",
                        metadata={
                            "classification": "BLANK",
                            "quality": native_quality,
                            "ocr_regions": [],
                            "render_dpi": None,
                            "geometry": geometry,
                        },
                    )
                else:
                    classification = self._classification(
                        has_text_ops, has_vectors, has_images
                    )
                    ocr_pages += 1
                    if ocr_pages > limits.maximum_ocr_pages:
                        code = "OCR_PAGE_LIMIT"
                        first_failure = first_failure or (
                            code,
                            "PDF requires OCR on more pages than the configured limit",
                            422,
                        )
                        issue_counts[code] += 1
                        units.append(self._failed_unit(index, page_number, code, "OCR"))
                        continue

                    if rendered_document is None:
                        try:
                            rendered_document = pdfium.PdfDocument(data)
                        except Exception:
                            code = "PDF_RENDER_ERROR"
                            first_failure = first_failure or (
                                code,
                                "PDF pages could not be rendered safely",
                                422,
                            )
                            issue_counts[code] += 1
                            units.append(
                                self._failed_unit(index, page_number, code, "RENDER")
                            )
                            continue

                    try:
                        image, pixels = self._render_page(
                            rendered_document,
                            index,
                            limits.render_dpi,
                            limits.maximum_rendered_pixels_per_page,
                            page_count,
                        )
                    except AdapterError as exc:
                        first_failure = first_failure or (
                            exc.code,
                            exc.public_message,
                            exc.status_code,
                        )
                        issue_counts[exc.code] += 1
                        units.append(
                            self._failed_unit(index, page_number, exc.code, "RENDER")
                        )
                        continue

                    total_rendered_pixels += pixels
                    if total_rendered_pixels > limits.maximum_total_rendered_pixels:
                        image.close()
                        code = "PDF_RENDER_RESOURCE_LIMIT"
                        first_failure = first_failure or (
                            code,
                            "PDF rendering exceeded the configured resource limit",
                            422,
                        )
                        issue_counts[code] += 1
                        units.append(
                            self._failed_unit(index, page_number, code, "RENDER")
                        )
                        continue

                    try:
                        result = context.ocr_provider.recognize(
                            image, limits.ocr_timeout_seconds_per_page
                        )
                    except OCRError as exc:
                        first_failure = first_failure or (
                            exc.code,
                            exc.public_message,
                            exc.status_code,
                        )
                        issue_counts[exc.code] += 1
                        units.append(
                            self._failed_unit(index, page_number, exc.code, "OCR")
                        )
                        continue
                    finally:
                        image.close()

                    ocr_text = clean_extracted_text(result.text)
                    ocr_quality = _quality_metrics(ocr_text)
                    if not self._ocr_is_usable(
                        ocr_text,
                        result.confidence,
                        limits.ocr_minimum_characters,
                        limits.minimum_printable_ratio,
                        limits.minimum_ocr_confidence,
                    ):
                        code = "OCR_NO_USABLE_TEXT"
                        first_failure = first_failure or (
                            code,
                            f"OCR could not recover trustworthy text from PDF page {page_number}",
                            422,
                        )
                        issue_counts[code] += 1
                        units.append(self._failed_unit(index, page_number, code, "OCR"))
                        continue

                    warnings.append(f"PAGE_{page_number}_OCR_FALLBACK")
                    unit = ContentUnitDraft(
                        ordinal=index,
                        kind="PAGE",
                        text=ocr_text,
                        locator={"v": 1, "type": "pdf_page", "page": page_number},
                        extraction_method="OCR",
                        language=result.language,
                        confidence=result.confidence,
                        metadata={
                            "classification": classification,
                            "quality": ocr_quality,
                            "ocr_regions": list(result.regions),
                            "render_dpi": limits.render_dpi,
                            "geometry": geometry,
                        },
                    )

                total_characters += unit.character_count
                if total_characters > limits.maximum_extracted_characters:
                    issue_counts["EXTRACTED_CONTENT_LIMIT"] += 1
                    raise AdapterError(
                        "EXTRACTED_CONTENT_LIMIT",
                        "Extracted text exceeded the configured content limit",
                        422,
                        page_count,
                        failure_stage="NORMALIZATION",
                        diagnostics=self._diagnostics(
                            page_count,
                            [*units, unit],
                            method_counts,
                            issue_counts,
                            ocr_pages,
                            total_rendered_pixels,
                        ),
                    )
                method_counts[unit.extraction_method] += 1
                units.append(unit)
        finally:
            if rendered_document is not None:
                rendered_document.close()

        diagnostics = self._diagnostics(
            page_count,
            units,
            method_counts,
            issue_counts,
            ocr_pages,
            total_rendered_pixels,
        )
        usable_count = sum(unit.status == "USABLE" and bool(unit.text) for unit in units)
        if not usable_count:
            if first_failure is not None:
                code, message, status_code = first_failure
                raise AdapterError(
                    code,
                    message,
                    status_code,
                    page_count,
                    failure_stage="OCR" if code.startswith("OCR") else "EXTRACTION",
                    diagnostics=diagnostics,
                )
            raise AdapterError(
                "NO_EXTRACTABLE_TEXT",
                "PDF contains no extractable or recognizable text",
                422,
                page_count,
                diagnostics=diagnostics,
            )

        outcome = "PARTIAL" if any(unit.status == "FAILED" for unit in units) else "COMPLETE"
        return CanonicalDocument(
            source_format=self.source_format,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            units=tuple(units),
            page_count=page_count,
            warnings=tuple(warnings),
            outcome=outcome,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _read_bounded(source: BinaryIO, maximum_file_bytes: int) -> bytes:
        try:
            source.seek(0)
            data = source.read(maximum_file_bytes + 1)
        except (OSError, ValueError, AttributeError) as exc:
            raise AdapterError(
                "STORAGE_READ_ERROR",
                "Stored document could not be read",
                503,
                failure_stage="STORAGE",
            ) from exc
        if not data or len(data) > maximum_file_bytes:
            raise AdapterError(
                "DOCUMENT_SIZE_LIMIT",
                "The stored document exceeds the configured processing limit",
                422,
                failure_stage="VALIDATION",
            )
        if not data.startswith(b"%PDF-"):
            raise AdapterError(
                "FILE_TYPE_MISMATCH",
                "Stored content is not a valid PDF",
                422,
                failure_stage="VALIDATION",
            )
        return data

    @staticmethod
    def _open_reader(data: bytes) -> tuple[PdfReader, int]:
        try:
            reader = PdfReader(BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise AdapterError(
                    "ENCRYPTED_PDF",
                    "Encrypted or password-protected PDFs are not supported",
                    422,
                    failure_stage="VALIDATION",
                )
            return reader, len(reader.pages)
        except AdapterError:
            raise
        except (PdfReadError, OSError, ValueError, TypeError, KeyError) as exc:
            raise AdapterError(
                "PDF_EXTRACTION_ERROR",
                "PDF text extraction failed",
                422,
                failure_stage="PARSING",
            ) from exc

    @staticmethod
    def _failed_unit(
        ordinal: int, page_number: int, issue_code: str, method: str
    ) -> ContentUnitDraft:
        return ContentUnitDraft(
            ordinal=ordinal,
            kind="PAGE",
            text="",
            locator={"v": 1, "type": "pdf_page", "page": page_number},
            extraction_method=f"{method}_FAILED",
            status="FAILED",
            issue_code=issue_code,
            metadata={
                "classification": "UNRECOVERED",
                "quality": _quality_metrics(""),
                "ocr_regions": [],
                "render_dpi": None,
            },
        )

    @staticmethod
    def _is_blank(
        native_text: str,
        has_content: bool,
        has_text_ops: bool,
        has_vectors: bool,
        has_images: bool,
    ) -> bool:
        return (not has_content and not has_images and not has_vectors) or (
            not native_text and has_text_ops and not has_images and not has_vectors
        )

    @staticmethod
    def _classification(
        has_text_ops: bool, has_vectors: bool, has_images: bool
    ) -> str:
        if has_images and not has_vectors and not has_text_ops:
            return "IMAGE_ONLY"
        if has_vectors and not has_text_ops:
            return "VECTOR_OUTLINE_TEXT"
        return "MIXED"

    @staticmethod
    def _native_is_usable(
        text: str, has_text_operators: bool, minimum_characters: int, printable_ratio: float
    ) -> bool:
        metrics = _quality_metrics(text)
        if (
            not text
            or metrics["printable_ratio"] < printable_ratio
            or metrics["replacement_ratio"] > 0.02
            or (len(text) >= 20 and metrics["longest_repeated_run_ratio"] > 0.5)
        ):
            return False
        if len(text) >= minimum_characters and metrics["alphanumeric_characters"] >= 3:
            return True
        return has_text_operators and metrics["alphanumeric_characters"] > 0

    @staticmethod
    def _ocr_is_usable(
        text: str,
        confidence: float | None,
        minimum_characters: int,
        printable_ratio: float,
        minimum_confidence: float,
    ) -> bool:
        metrics = _quality_metrics(text)
        return (
            len(text) >= minimum_characters
            and metrics["printable_ratio"] >= printable_ratio
            and metrics["alphanumeric_characters"] >= 3
            and metrics["replacement_ratio"] <= 0.02
            and not (len(text) >= 20 and metrics["longest_repeated_run_ratio"] > 0.5)
            and (confidence is None or confidence >= minimum_confidence)
        )

    @staticmethod
    def _diagnostics(
        page_count: int,
        units: list[ContentUnitDraft],
        method_counts: Counter[str],
        issue_counts: Counter[str],
        ocr_pages: int,
        total_rendered_pixels: int,
    ) -> dict:
        confidences = [unit.confidence for unit in units if unit.confidence is not None]
        return {
            "page_count": page_count,
            "unit_count": len(units),
            "usable_unit_count": sum(unit.status == "USABLE" for unit in units),
            "skipped_unit_count": sum(unit.status == "SKIPPED" for unit in units),
            "failed_unit_count": sum(unit.status == "FAILED" for unit in units),
            "method_counts": dict(sorted(method_counts.items())),
            "issue_counts": dict(sorted(issue_counts.items())),
            "ocr_candidate_count": ocr_pages,
            "rendered_pixel_count": total_rendered_pixels,
            "average_ocr_confidence": (
                round(sum(confidences) / len(confidences), 4) if confidences else None
            ),
        }

    @staticmethod
    def _render_page(
        document,
        page_index: int,
        dpi: int,
        maximum_pixels: int,
        page_count: int,
    ):
        page = None
        bitmap = None
        try:
            page = document[page_index]
            scale = dpi / 72.0
            width = max(1, round(page.get_width() * scale))
            height = max(1, round(page.get_height() * scale))
            pixels = width * height
            if pixels > maximum_pixels:
                raise AdapterError(
                    "PDF_RENDER_RESOURCE_LIMIT",
                    "A PDF page exceeds the configured rendering limit",
                    422,
                    page_count,
                    failure_stage="RENDERING",
                )
            bitmap = page.render(scale=scale)
            return bitmap.to_pil().copy(), pixels
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(
                "PDF_RENDER_ERROR",
                "A PDF page could not be rendered safely",
                422,
                page_count,
                failure_stage="RENDERING",
            ) from exc
        finally:
            if bitmap is not None:
                bitmap.close()
            if page is not None:
                page.close()
