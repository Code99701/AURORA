from collections.abc import Iterable
from pathlib import Path

from app.ingestion.base import AdapterError, FormatAdapter


class AdapterRegistry:
    """Explicit allowlisted adapter selection boundary."""

    def __init__(self, adapters: Iterable[FormatAdapter] = ()):
        self._adapters: dict[str, FormatAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: FormatAdapter) -> None:
        if adapter.source_format in self._adapters:
            raise ValueError(f"Adapter already registered for {adapter.source_format}")
        self._adapters[adapter.source_format] = adapter

    def resolve(self, source_format: str) -> FormatAdapter:
        try:
            return self._adapters[source_format]
        except KeyError as exc:
            raise AdapterError(
                "UNSUPPORTED_FILE_TYPE",
                "This document type is not supported by the ingestion service",
                415,
            ) from exc

    def resolve_document(self, media_type: str, filename: str) -> FormatAdapter:
        """Resolve only when validated media type and normalized extension agree."""
        extension = Path(filename).suffix.casefold()
        matches = [
            adapter
            for adapter in self._adapters.values()
            if (
                media_type.casefold() in {
                    value.casefold() for value in adapter.capabilities.media_types
                }
                and extension in {
                    value.casefold() for value in adapter.capabilities.extensions
                }
            )
        ]
        if len(matches) != 1:
            raise AdapterError(
                "UNSUPPORTED_FILE_TYPE",
                "This document type is not supported by the ingestion service",
                415,
                failure_stage="FORMAT_DETECTION",
            )
        return matches[0]

    def capabilities(self) -> dict[str, object]:
        """Return an immutable-by-convention capability snapshot for diagnostics."""
        return {
            source_format: adapter.capabilities
            for source_format, adapter in self._adapters.items()
        }


_registry: AdapterRegistry | None = None


def get_adapter_registry() -> AdapterRegistry:
    global _registry
    if _registry is None:
        from app.ingestion.docx import DOCXAdapter
        from app.ingestion.pdf import PDFAdapter
        from app.ingestion.pptx import PPTXAdapter
        from app.ingestion.tabular import CSVAdapter, TSVAdapter
        from app.ingestion.text import MarkdownAdapter, TXTAdapter
        from app.ingestion.xlsx import XLSXAdapter

        _registry = AdapterRegistry(
            [
                PDFAdapter(),
                TXTAdapter(),
                MarkdownAdapter(),
                CSVAdapter(),
                TSVAdapter(),
                DOCXAdapter(),
                XLSXAdapter(),
                PPTXAdapter(),
            ]
        )
    return _registry
