from app.core.config import settings
from app.ocr.base import OCRProvider
from app.ocr.tesseract import TesseractOCRProvider


def get_ocr_provider() -> OCRProvider:
    return TesseractOCRProvider(
        languages=settings.OCR_LANGUAGES,
        executable=settings.TESSERACT_EXECUTABLE,
    )
