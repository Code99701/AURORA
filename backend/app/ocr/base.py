from dataclasses import dataclass
from typing import Protocol

from PIL.Image import Image


class OCRError(Exception):
    def __init__(self, code: str, public_message: str, status_code: int = 422):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float | None
    language: str
    regions: tuple[dict, ...] = ()


class OCRProvider(Protocol):
    provider_name: str

    def recognize(self, image: Image, timeout_seconds: float) -> OCRResult: ...
