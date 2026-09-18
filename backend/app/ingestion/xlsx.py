from collections import Counter
from datetime import date, datetime, time
from io import BytesIO
from pathlib import PurePosixPath
from typing import BinaryIO
from xml.etree import ElementTree
from zipfile import ZipFile

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from app.ingestion.base import (
    AdapterCapabilities,
    AdapterError,
    ContentUnitDraft,
    ExtractionContext,
)
from app.ingestion.common import finalize_document, read_bounded
from app.ingestion.detection import inspect_ooxml_archive


_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _resolve_package_target(base: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    parts: list[str] = []
    for part in PurePosixPath(base, target).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part not in {"", "."}:
            parts.append(part)
    return "/".join(parts)


def _worksheet_structure(data: bytes) -> tuple[dict[str, dict], list[dict], int]:
    """Read structural metadata directly without materializing worksheet cells."""
    with ZipFile(BytesIO(data)) as archive:
        workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationship_root = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        targets = {
            relationship.attrib["Id"]: _resolve_package_target(
                "xl", relationship.attrib["Target"]
            )
            for relationship in relationship_root.findall(f"{{{_PKG_REL_NS}}}Relationship")
            if "Id" in relationship.attrib and "Target" in relationship.attrib
        }
        structure: dict[str, dict] = {}
        for sheet in workbook_root.findall(f".//{{{_MAIN_NS}}}sheet"):
            name = sheet.attrib.get("name", "")
            relationship_id = sheet.attrib.get(f"{{{_DOC_REL_NS}}}id")
            target = targets.get(relationship_id or "")
            if not name or not target or target not in archive.namelist():
                continue
            root = ElementTree.fromstring(archive.read(target))
            merged_ranges = [
                element.attrib["ref"]
                for element in root.findall(f".//{{{_MAIN_NS}}}mergeCell")
                if element.attrib.get("ref")
            ]
            hidden_rows = [
                int(element.attrib["r"])
                for element in root.findall(f".//{{{_MAIN_NS}}}row")
                if element.attrib.get("hidden") in {"1", "true"}
                and element.attrib.get("r", "").isdigit()
            ]
            hidden_columns = [
                {
                    "minimum": int(element.attrib.get("min", "0")),
                    "maximum": int(element.attrib.get("max", "0")),
                }
                for element in root.findall(f".//{{{_MAIN_NS}}}col")
                if element.attrib.get("hidden") in {"1", "true"}
            ]
            dimension = root.find(f"{{{_MAIN_NS}}}dimension")
            table_parts = root.find(f"{{{_MAIN_NS}}}tableParts")
            structure[name] = {
                "declared_used_range": (
                    dimension.attrib.get("ref") if dimension is not None else None
                ),
                "merged_ranges": merged_ranges,
                "hidden_rows": hidden_rows,
                "hidden_columns": hidden_columns,
                "table_part_count": int(
                    table_parts.attrib.get("count", "0")
                    if table_parts is not None
                    else 0
                ),
            }

        tables: list[dict] = []
        for name in sorted(
            entry for entry in archive.namelist() if entry.startswith("xl/tables/") and entry.endswith(".xml")
        ):
            root = ElementTree.fromstring(archive.read(name))
            tables.append(
                {
                    "name": root.attrib.get("name"),
                    "display_name": root.attrib.get("displayName"),
                    "range": root.attrib.get("ref"),
                }
            )
        external_link_count = sum(
            name.startswith("xl/externalLinks/") and name.endswith(".xml")
            for name in archive.namelist()
        )
        return structure, tables, external_link_count


def _value_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)


class XLSXAdapter:
    adapter_id = "aurora.xlsx"
    adapter_version = "1.0"
    source_format = "xlsx"
    capabilities = AdapterCapabilities(
        extensions=(".xlsx",),
        media_types=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        unit_kinds=("WORKSHEET_RANGE",),
        supports_partial_results=True,
        supports_native_extraction=True,
        supports_ocr_fallback=False,
    )

    def extract(self, source: BinaryIO, context: ExtractionContext):
        data = read_bounded(source, context.limits.maximum_file_bytes)
        try:
            archive = inspect_ooxml_archive(
                BytesIO(data),
                required_member="xl/workbook.xml",
                maximum_entries=context.limits.maximum_archive_entries,
                maximum_uncompressed_bytes=context.limits.maximum_archive_uncompressed_bytes,
            )
            sheet_structure, defined_tables, external_link_count = _worksheet_structure(data)
            formula_book = load_workbook(
                BytesIO(data), read_only=True, data_only=False, keep_links=False
            )
            cached_book = load_workbook(
                BytesIO(data), read_only=True, data_only=True, keep_links=False
            )
        except (InvalidFileException, ValueError, KeyError, OSError) as exc:
            raise AdapterError(
                "XLSX_PARSE_ERROR",
                "Excel workbook could not be parsed safely",
                422,
                failure_stage="PARSING",
            ) from exc
        except Exception as exc:
            raise AdapterError(
                "XLSX_PARSE_ERROR",
                "Excel workbook could not be parsed safely",
                422,
                failure_stage="PARSING",
            ) from exc

        if len(formula_book.sheetnames) > context.limits.maximum_sheets:
            formula_book.close()
            cached_book.close()
            raise AdapterError(
                "XLSX_SHEET_LIMIT",
                "Workbook exceeds the configured worksheet limit",
                422,
                failure_stage="EXTRACTION",
            )
        sheet_count = len(formula_book.sheetnames)

        units: list[ContentUnitDraft] = []
        sheet_diagnostics: list[dict] = []
        total_cells = 0
        formula_count = 0
        cached_formula_count = 0
        failed_sheets = 0

        try:
            for sheet_order, sheet_name in enumerate(formula_book.sheetnames, start=1):
                sheet = formula_book[sheet_name]
                cached_sheet = cached_book[sheet_name]
                try:
                    maximum_row = int(sheet.max_row or 0)
                    maximum_column = int(sheet.max_column or 0)
                    if maximum_row > context.limits.maximum_rows:
                        raise AdapterError(
                            "TABULAR_ROW_LIMIT",
                            "Worksheet exceeds the configured row limit",
                            422,
                            failure_stage="EXTRACTION",
                        )
                    if maximum_column > context.limits.maximum_columns:
                        raise AdapterError(
                            "TABULAR_COLUMN_LIMIT",
                            "Worksheet exceeds the configured column limit",
                            422,
                            failure_stage="EXTRACTION",
                        )
                    rectangular_cells = maximum_row * maximum_column
                    total_cells += rectangular_cells
                    if total_cells > context.limits.maximum_table_cells:
                        raise AdapterError(
                            "TABULAR_CELL_LIMIT",
                            "Workbook exceeds the configured cell limit",
                            422,
                            failure_stage="EXTRACTION",
                        )

                    group_lines: list[str] = []
                    group_start = 0
                    group_end = 0
                    group_min_column: int | None = None
                    group_max_column: int | None = None
                    used_rows = 0
                    type_counts: Counter[str] = Counter()

                    def emit_group() -> None:
                        nonlocal group_lines, group_start, group_end
                        nonlocal group_min_column, group_max_column
                        if not group_lines or group_min_column is None or group_max_column is None:
                            return
                        range_label = (
                            f"{get_column_letter(group_min_column)}{group_start}:"
                            f"{get_column_letter(group_max_column)}{group_end}"
                        )
                        units.append(
                            ContentUnitDraft(
                                ordinal=len(units),
                                kind="WORKSHEET_RANGE",
                                text="\n".join(group_lines),
                                locator={
                                    "v": 1,
                                    "type": "xlsx_range",
                                    "sheet": sheet_name,
                                    "sheet_order": sheet_order,
                                    "range": range_label,
                                    "row_start": group_start,
                                    "row_end": group_end,
                                },
                                extraction_method="NATIVE",
                                content_type=self.capabilities.media_types[0],
                                metadata={
                                    "sheet_state": sheet.sheet_state,
                                    "cell_type_counts": dict(sorted(type_counts.items())),
                                    **sheet_structure.get(sheet_name, {}),
                                },
                            )
                        )
                        group_lines = []
                        group_start = 0
                        group_end = 0
                        group_min_column = None
                        group_max_column = None
                        type_counts.clear()

                    formula_rows = sheet.iter_rows()
                    cached_rows = cached_sheet.iter_rows()
                    for row_number, (formula_row, cached_row) in enumerate(
                        zip(formula_rows, cached_rows, strict=False), start=1
                    ):
                        rendered_cells: list[str] = []
                        row_min: int | None = None
                        row_max: int | None = None
                        for formula_cell, cached_cell in zip(
                            formula_row, cached_row, strict=False
                        ):
                            value = formula_cell.value
                            if value is None:
                                continue
                            coordinate = formula_cell.coordinate
                            column = formula_cell.column
                            row_min = column if row_min is None else min(row_min, column)
                            row_max = column if row_max is None else max(row_max, column)
                            data_type = formula_cell.data_type or "unknown"
                            type_counts[data_type] += 1
                            if data_type == "f":
                                formula_count += 1
                                formula_text = _value_text(value)
                                cached_text = _value_text(cached_cell.value)
                                if cached_text:
                                    cached_formula_count += 1
                                    rendered = (
                                        f"{coordinate} [formula]: {formula_text} "
                                        f"[cached value]: {cached_text}"
                                    )
                                else:
                                    rendered = f"{coordinate} [formula]: {formula_text} [cached value unavailable]"
                            else:
                                rendered = f"{coordinate}: {_value_text(value)}"
                            if len(rendered) > context.limits.maximum_field_characters:
                                raise AdapterError(
                                    "TABULAR_FIELD_LIMIT",
                                    "A worksheet cell exceeds the configured text limit",
                                    422,
                                    failure_stage="EXTRACTION",
                                )
                            rendered_cells.append(rendered)
                        if not rendered_cells:
                            continue
                        used_rows += 1
                        if not group_lines:
                            group_start = row_number
                        group_end = row_number
                        group_min_column = (
                            row_min
                            if group_min_column is None
                            else min(group_min_column, row_min or group_min_column)
                        )
                        group_max_column = (
                            row_max
                            if group_max_column is None
                            else max(group_max_column, row_max or group_max_column)
                        )
                        group_lines.append(f"Row {row_number}: " + " | ".join(rendered_cells))
                        if len(group_lines) >= context.limits.tabular_rows_per_unit:
                            emit_group()
                    emit_group()

                    if used_rows == 0:
                        units.append(
                            ContentUnitDraft(
                                ordinal=len(units),
                                kind="WORKSHEET_RANGE",
                                text="",
                                locator={
                                    "v": 1,
                                    "type": "xlsx_sheet",
                                    "sheet": sheet_name,
                                    "sheet_order": sheet_order,
                                },
                                extraction_method="NATIVE",
                                content_type=self.capabilities.media_types[0],
                                status="SKIPPED",
                                issue_code="EMPTY_WORKSHEET",
                                metadata={
                                    "sheet_state": sheet.sheet_state,
                                    **sheet_structure.get(sheet_name, {}),
                                },
                            )
                        )
                    sheet_diagnostics.append(
                        {
                            "sheet_order": sheet_order,
                            "state": sheet.sheet_state,
                            "maximum_row": maximum_row,
                            "maximum_column": maximum_column,
                            "used_row_count": used_rows,
                        }
                    )
                except AdapterError:
                    raise
                except Exception:
                    failed_sheets += 1
                    units.append(
                        ContentUnitDraft(
                            ordinal=len(units),
                            kind="WORKSHEET_RANGE",
                            text="",
                            locator={
                                "v": 1,
                                "type": "xlsx_sheet",
                                "sheet": sheet_name,
                                "sheet_order": sheet_order,
                            },
                            extraction_method="NATIVE_FAILED",
                            content_type=self.capabilities.media_types[0],
                            status="FAILED",
                            issue_code="XLSX_WORKSHEET_ERROR",
                        )
                    )
        finally:
            formula_book.close()
            cached_book.close()

        return finalize_document(
            source_format=self.source_format,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            units=units,
            limits=context.limits,
            diagnostics={
                **archive,
                "sheet_count": sheet_count,
                "failed_sheet_count": failed_sheets,
                "rectangular_cell_count": total_cells,
                "formula_count": formula_count,
                "cached_formula_count": cached_formula_count,
                "formula_calculation_performed": False,
                "defined_tables": defined_tables,
                "external_link_count": external_link_count,
                "sheets": sheet_diagnostics,
            },
        )
