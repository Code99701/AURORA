from dataclasses import dataclass
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfExtractionError(Exception):
    """Raised when a stored object cannot be interpreted as a text PDF."""


@dataclass(frozen=True)
class ExtractedPdfPage:
    page_number: int
    text: str


def extract_pdf_pages(source: BinaryIO) -> list[ExtractedPdfPage]:
    """Extract raw text page-by-page from a seekable binary stream."""
    try:
        reader = PdfReader(source, strict=False)
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    raise PdfExtractionError("Encrypted PDFs are not supported")
            except PdfExtractionError:
                raise
            except Exception as exc:
                raise PdfExtractionError("Encrypted PDFs are not supported") from exc

        pages: list[ExtractedPdfPage] = []
        for page_number, page in enumerate(reader.pages, start=1):
            pages.append(
                ExtractedPdfPage(
                    page_number=page_number,
                    text=page.extract_text() or "",
                )
            )
        return pages
    except PdfExtractionError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError, KeyError) as exc:
        raise PdfExtractionError("PDF text extraction failed") from exc
