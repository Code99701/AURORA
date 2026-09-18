import shutil
from pathlib import Path

import pytesseract
from PIL.Image import Image

from app.ocr.base import OCRError, OCRResult


class TesseractOCRProvider:
    provider_name = "tesseract"

    def __init__(self, languages: str, executable: str | None = None):
        self.languages = languages
        resolved = executable or shutil.which("tesseract")
        if resolved is None:
            common_windows_path = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
            if common_windows_path.is_file():
                resolved = str(common_windows_path)
        if resolved is None:
            project_local_path = (
                Path(__file__).resolve().parents[2]
                / ".runtime"
                / "tesseract"
                / "tesseract.exe"
            )
            if project_local_path.is_file():
                resolved = str(project_local_path)
        self.executable = resolved

    def _configure(self) -> None:
        if not self.executable:
            raise OCRError(
                "OCR_ENGINE_UNAVAILABLE",
                "OCR is required for this PDF, but the local OCR engine is unavailable",
                503,
            )
        pytesseract.pytesseract.tesseract_cmd = self.executable
        try:
            available = set(pytesseract.get_languages(config=""))
        except (pytesseract.TesseractNotFoundError, OSError) as exc:
            raise OCRError(
                "OCR_ENGINE_UNAVAILABLE",
                "OCR is required for this PDF, but the local OCR engine is unavailable",
                503,
            ) from exc
        requested = set(self.languages.split("+"))
        missing = requested - available
        if missing:
            raise OCRError(
                "OCR_LANGUAGE_UNAVAILABLE",
                "OCR language data required for this document is unavailable",
                503,
            )

    def recognize(self, image: Image, timeout_seconds: float) -> OCRResult:
        self._configure()
        try:
            data = pytesseract.image_to_data(
                image.convert("RGB"),
                lang=self.languages,
                config="--oem 1 --psm 3",
                output_type=pytesseract.Output.DICT,
                timeout=timeout_seconds,
            )
        except RuntimeError as exc:
            raise OCRError(
                "OCR_TIMEOUT", "OCR exceeded the allowed processing time", 422
            ) from exc
        except pytesseract.TesseractError as exc:
            raise OCRError(
                "OCR_PROCESSING_ERROR", "The PDF page could not be recognized safely", 422
            ) from exc
        except (OSError, ValueError) as exc:
            raise OCRError(
                "OCR_PROCESSING_ERROR", "The PDF page could not be recognized safely", 422
            ) from exc

        words: list[str] = []
        confidences: list[float] = []
        regions: list[dict] = []
        for index, raw_text in enumerate(data.get("text", [])):
            word = str(raw_text).strip()
            if not word:
                continue
            try:
                raw_confidence = float(data["conf"][index])
            except (KeyError, IndexError, TypeError, ValueError):
                raw_confidence = -1
            words.append(word)
            if raw_confidence >= 0:
                confidences.append(raw_confidence / 100.0)
            regions.append(
                {
                    "x": int(data["left"][index]),
                    "y": int(data["top"][index]),
                    "width": int(data["width"][index]),
                    "height": int(data["height"][index]),
                    "confidence": max(0.0, raw_confidence / 100.0),
                }
            )
        confidence = sum(confidences) / len(confidences) if confidences else None
        return OCRResult(
            text=" ".join(words),
            confidence=confidence,
            language=self.languages,
            regions=tuple(regions),
        )
