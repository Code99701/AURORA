import csv
from io import StringIO
from typing import BinaryIO

from app.ingestion.base import (
    AdapterCapabilities,
    AdapterError,
    ContentUnitDraft,
    ExtractionContext,
)
from app.ingestion.common import decode_utf8, finalize_document, read_bounded


def _column_name(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return f"Column {result}"


class DelimitedTextAdapter:
    delimiter: str | None = None

    def extract(self, source: BinaryIO, context: ExtractionContext):
        data = read_bounded(source, context.limits.maximum_file_bytes)
        decoded, replaced = decode_utf8(data)
        sample = decoded[: min(len(decoded), 65_536)]
        delimiter = self.delimiter
        if delimiter is None:
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
            except csv.Error:
                delimiter = ","
        try:
            has_header = csv.Sniffer().has_header(sample)
        except csv.Error:
            has_header = False

        previous_field_limit = csv.field_size_limit()
        csv.field_size_limit(context.limits.maximum_field_characters)
        units: list[ContentUnitDraft] = []
        row_group: list[tuple[int, list[str]]] = []
        row_count = 0
        cell_count = 0
        empty_rows = 0
        inconsistent_rows = 0
        formula_like_values = 0
        header: list[str] | None = None
        expected_width: int | None = None

        def emit_group() -> None:
            nonlocal row_group
            if not row_group:
                return
            rendered: list[str] = []
            for row_number, values in row_group:
                labels = header or [_column_name(index) for index in range(len(values))]
                pairs = []
                for index, value in enumerate(values):
                    if not value:
                        continue
                    label = labels[index] if index < len(labels) and labels[index] else _column_name(index)
                    pairs.append(f"{label}: {value.replace(chr(10), ' ⏎ ')}")
                if pairs:
                    rendered.append(f"Row {row_number}: " + " | ".join(pairs))
            text = "\n".join(rendered)
            if text:
                units.append(
                    ContentUnitDraft(
                        ordinal=len(units),
                        kind="ROW_GROUP",
                        text=text,
                        locator={
                            "v": 1,
                            "type": "delimited_rows",
                            "row_start": row_group[0][0],
                            "row_end": row_group[-1][0],
                        },
                        extraction_method="NATIVE",
                        content_type=self.capabilities.media_types[0],
                        metadata={
                            "delimiter": delimiter,
                            "has_header": has_header,
                            "column_count": max(len(values) for _, values in row_group),
                        },
                    )
                )
            row_group = []

        try:
            reader = csv.reader(
                StringIO(decoded, newline=""), delimiter=delimiter, strict=True
            )
            for physical_row, values in enumerate(reader, start=1):
                row_count += 1
                if row_count > context.limits.maximum_rows:
                    raise AdapterError(
                        "TABULAR_ROW_LIMIT",
                        "Tabular source exceeds the configured row limit",
                        422,
                        failure_stage="EXTRACTION",
                    )
                if len(values) > context.limits.maximum_columns:
                    raise AdapterError(
                        "TABULAR_COLUMN_LIMIT",
                        "Tabular source exceeds the configured column limit",
                        422,
                        failure_stage="EXTRACTION",
                    )
                cell_count += len(values)
                if cell_count > context.limits.maximum_table_cells:
                    raise AdapterError(
                        "TABULAR_CELL_LIMIT",
                        "Tabular source exceeds the configured cell limit",
                        422,
                        failure_stage="EXTRACTION",
                    )
                if any(len(value) > context.limits.maximum_field_characters for value in values):
                    raise AdapterError(
                        "TABULAR_FIELD_LIMIT",
                        "A tabular field exceeds the configured text limit",
                        422,
                        failure_stage="EXTRACTION",
                    )
                values = [value.strip() for value in values]
                if not any(values):
                    empty_rows += 1
                    continue
                if header is None and has_header:
                    header = [value or _column_name(index) for index, value in enumerate(values)]
                    expected_width = len(header)
                    continue
                if expected_width is None:
                    expected_width = len(values)
                elif len(values) != expected_width:
                    inconsistent_rows += 1
                formula_like_values += sum(
                    bool(value) and value[0] in "=+-@" for value in values
                )
                row_group.append((physical_row, values))
                if len(row_group) >= context.limits.tabular_rows_per_unit:
                    emit_group()
            emit_group()
        except csv.Error as exc:
            raise AdapterError(
                "DELIMITED_TEXT_PARSE_ERROR",
                "Delimited text could not be parsed safely",
                422,
                failure_stage="PARSING",
            ) from exc
        finally:
            csv.field_size_limit(previous_field_limit)

        warnings = ["INVALID_UTF8_REPLACED"] if replaced else []
        if inconsistent_rows:
            warnings.append("INCONSISTENT_ROW_WIDTHS")
        return finalize_document(
            source_format=self.source_format,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            units=units,
            limits=context.limits,
            warnings=warnings,
            diagnostics={
                "row_count": row_count,
                "cell_count": cell_count,
                "empty_row_count": empty_rows,
                "inconsistent_row_count": inconsistent_rows,
                "formula_like_value_count": formula_like_values,
                "delimiter": delimiter,
                "has_header": has_header,
                "encoding": "utf-8",
                "invalid_unicode_replaced": replaced,
            },
        )


class CSVAdapter(DelimitedTextAdapter):
    adapter_id = "aurora.csv"
    adapter_version = "1.0"
    source_format = "csv"
    capabilities = AdapterCapabilities(
        extensions=(".csv",),
        media_types=("text/csv", "application/csv", "text/plain"),
        unit_kinds=("ROW_GROUP",),
        supports_partial_results=False,
        supports_native_extraction=True,
        supports_ocr_fallback=False,
    )


class TSVAdapter(DelimitedTextAdapter):
    adapter_id = "aurora.tsv"
    adapter_version = "1.0"
    source_format = "tsv"
    delimiter = "\t"
    capabilities = AdapterCapabilities(
        extensions=(".tsv",),
        media_types=("text/tab-separated-values", "text/tsv", "text/plain"),
        unit_kinds=("ROW_GROUP",),
        supports_partial_results=False,
        supports_native_extraction=True,
        supports_ocr_fallback=False,
    )
