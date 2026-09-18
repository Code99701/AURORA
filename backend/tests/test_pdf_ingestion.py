from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from app.ingestion.base import AdapterError, ExtractionContext, ExtractionLimits
from app.ingestion.pdf import PDFAdapter
from app.ingestion.registry import AdapterRegistry
from app.ocr.base import OCRError, OCRResult
from tests.test_processing import build_text_pdf
from tests.adapter_compliance import (
    assert_adapter_capabilities,
    assert_canonical_document_contract,
)


def build_vector_pdf() -> bytes:
    stream = b"72 700 m 90 730 l 108 700 l h f 116 700 m 134 730 l 152 700 l h f"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    return _serialize_pdf(objects)


def build_image_pdf() -> bytes:
    content = b"q 300 0 0 120 72 600 cm /Im1 Do Q"
    image = b"\xff"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /XObject << /Im1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        f"<< /Length {len(content)} >>\nstream\n".encode()
        + content
        + b"\nendstream",
        (
            b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
            b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\nstream\n"
            + image
            + b"\nendstream"
        ),
    ]
    return _serialize_pdf(objects)


def _serialize_pdf(objects: list[bytes]) -> bytes:
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)


def combine_pdfs(*documents: bytes) -> bytes:
    writer = PdfWriter()
    for document in documents:
        writer.append(BytesIO(document))
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def encrypt_pdf(document: bytes) -> bytes:
    writer = PdfWriter()
    writer.append(BytesIO(document))
    writer.encrypt("secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def rotate_pdf(document: bytes, degrees: int) -> bytes:
    reader = PdfReader(BytesIO(document))
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(degrees)
        writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class FakeOCR:
    provider_name = "fake"

    def __init__(self, text: str = "Recognized trustworthy research content", confidence=0.94):
        self.text = text
        self.confidence = confidence
        self.calls = 0

    def recognize(self, image, timeout_seconds):
        self.calls += 1
        assert image.width > 0 and image.height > 0
        assert timeout_seconds == 3
        return OCRResult(
            text=self.text,
            confidence=self.confidence,
            language="eng",
            regions=({"x": 1, "y": 2, "width": 3, "height": 4},),
        )


class TimeoutOCR:
    provider_name = "timeout"

    def recognize(self, image, timeout_seconds):
        raise OCRError("OCR_TIMEOUT", "OCR exceeded the allowed processing time", 422)


@pytest.fixture
def limits() -> ExtractionLimits:
    return ExtractionLimits(
        maximum_file_bytes=2_000_000,
        maximum_pages=10,
        render_dpi=72,
        maximum_rendered_pixels_per_page=1_000_000,
        maximum_total_rendered_pixels=2_000_000,
        maximum_ocr_pages=5,
        ocr_timeout_seconds_per_page=3,
        native_minimum_characters=8,
        ocr_minimum_characters=12,
        minimum_printable_ratio=0.85,
        minimum_ocr_confidence=0.25,
        maximum_extracted_characters=10_000,
    )


def extract(document: bytes, ocr, limits: ExtractionLimits):
    return PDFAdapter().extract(
        BytesIO(document), ExtractionContext(ocr_provider=ocr, limits=limits)
    )


def test_searchable_pdf_uses_native_text_without_ocr(limits):
    ocr = FakeOCR()
    result = extract(build_text_pdf(["Native searchable evidence"]), ocr, limits)
    assert ocr.calls == 0
    assert result.units[0].text == "Native searchable evidence"
    assert result.units[0].extraction_method == "NATIVE"
    assert result.units[0].locator == {"v": 1, "type": "pdf_page", "page": 1}
    assert_canonical_document_contract(result)


def test_pdf_adapter_declares_truthful_capabilities():
    adapter = PDFAdapter()
    assert_adapter_capabilities(adapter)
    assert adapter.capabilities.extensions == (".pdf",)
    assert adapter.capabilities.supports_partial_results is True


def test_registry_detects_only_matching_validated_media_type_and_extension():
    registry = AdapterRegistry([PDFAdapter()])
    assert registry.resolve_document("application/pdf", "research.PDF").source_format == "pdf"
    with pytest.raises(AdapterError) as error:
        registry.resolve_document("application/pdf", "spoofed.txt")
    assert error.value.code == "UNSUPPORTED_FILE_TYPE"


def test_scanned_image_pdf_renders_and_uses_ocr(limits):
    ocr = FakeOCR()
    result = extract(build_image_pdf(), ocr, limits)
    assert ocr.calls == 1
    assert result.units[0].extraction_method == "OCR"
    assert result.units[0].metadata["classification"] == "IMAGE_ONLY"
    assert result.units[0].confidence == pytest.approx(0.94)


def test_vector_outline_pdf_renders_and_uses_ocr(limits):
    ocr = FakeOCR()
    result = extract(build_vector_pdf(), ocr, limits)
    assert ocr.calls == 1
    assert result.units[0].extraction_method == "OCR"
    assert result.units[0].metadata["classification"] == "VECTOR_OUTLINE_TEXT"


def test_mixed_pdf_selectively_ocrs_only_the_insufficient_page(limits):
    ocr = FakeOCR()
    result = extract(
        combine_pdfs(
            build_text_pdf(["Native searchable first page"]), build_vector_pdf()
        ),
        ocr,
        limits,
    )
    assert ocr.calls == 1
    assert [unit.extraction_method for unit in result.units] == ["NATIVE", "OCR"]
    assert [unit.locator["page"] for unit in result.units] == [1, 2]


def test_mixed_pdf_preserves_native_page_when_ocr_page_fails(limits):
    result = extract(
        combine_pdfs(build_text_pdf(["Usable native evidence"]), build_vector_pdf()),
        TimeoutOCR(),
        limits,
    )
    assert result.outcome == "PARTIAL"
    assert [unit.status for unit in result.units] == ["USABLE", "FAILED"]
    assert result.units[1].issue_code == "OCR_TIMEOUT"
    assert result.diagnostics["usable_unit_count"] == 1
    assert result.diagnostics["failed_unit_count"] == 1
    assert result.diagnostics["issue_counts"] == {"OCR_TIMEOUT": 1}
    assert_canonical_document_contract(result)


def test_native_only_pdf_does_not_require_renderer(limits, monkeypatch):
    def renderer_must_not_open(*args, **kwargs):
        raise AssertionError("renderer must remain lazy for native-only PDFs")

    monkeypatch.setattr("app.ingestion.pdf.pdfium.PdfDocument", renderer_must_not_open)
    result = extract(build_text_pdf(["Native evidence without rendering"]), FakeOCR(), limits)
    assert result.outcome == "COMPLETE"
    assert result.units[0].extraction_method == "NATIVE"


def test_rotated_page_preserves_geometry_and_native_evidence(limits):
    result = extract(
        rotate_pdf(build_text_pdf(["Rotated native evidence"]), 90),
        FakeOCR(),
        limits,
    )
    assert result.units[0].text == "Rotated native evidence"
    assert result.units[0].metadata["geometry"] == {
        "width_points": 612.0,
        "height_points": 792.0,
        "rotation_degrees": 90,
    }


def test_blank_pdf_is_not_sent_to_ocr_and_fails(limits):
    ocr = FakeOCR()
    with pytest.raises(AdapterError) as error:
        extract(build_text_pdf([None]), ocr, limits)
    assert error.value.code == "NO_EXTRACTABLE_TEXT"
    assert ocr.calls == 0


def test_malformed_pdf_fails_safely(limits):
    with pytest.raises(AdapterError) as error:
        extract(b"%PDF-corrupt", FakeOCR(), limits)
    assert error.value.code == "PDF_EXTRACTION_ERROR"


def test_encrypted_pdf_is_rejected(limits):
    encrypted = encrypt_pdf(build_text_pdf(["Encrypted text"])); assert PdfReader(BytesIO(encrypted)).is_encrypted
    with pytest.raises(AdapterError) as error:
        extract(encrypted, FakeOCR(), limits)
    assert error.value.code == "ENCRYPTED_PDF"


def test_low_quality_ocr_does_not_mark_page_usable(limits):
    with pytest.raises(AdapterError) as error:
        extract(build_vector_pdf(), FakeOCR(text="few", confidence=0.9), limits)
    assert error.value.code == "OCR_NO_USABLE_TEXT"


def test_ocr_timeout_is_safe_and_actionable(limits):
    with pytest.raises(AdapterError) as error:
        extract(build_vector_pdf(), TimeoutOCR(), limits)
    assert error.value.code == "OCR_TIMEOUT"
    assert "allowed processing time" in error.value.public_message


def test_rendered_pixel_limit_is_enforced_before_ocr(limits):
    constrained = ExtractionLimits(
        **{**limits.__dict__, "maximum_rendered_pixels_per_page": 1}
    )
    ocr = FakeOCR()
    with pytest.raises(AdapterError) as error:
        extract(build_vector_pdf(), ocr, constrained)
    assert error.value.code == "PDF_RENDER_RESOURCE_LIMIT"
    assert ocr.calls == 0
