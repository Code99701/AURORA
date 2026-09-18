import re
from typing import BinaryIO

from app.ingestion.base import (
    AdapterCapabilities,
    ContentUnitDraft,
    ExtractionContext,
)
from app.ingestion.common import (
    decode_utf8,
    finalize_document,
    normalized_text,
    read_bounded,
)


HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
LINK = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _bounded_parts(text: str, maximum: int) -> list[tuple[str, int, int]]:
    if len(text) <= maximum:
        return [(text, 0, len(text))]
    return [
        (text[start : start + maximum], start, min(start + maximum, len(text)))
        for start in range(0, len(text), maximum)
    ]


class TXTAdapter:
    adapter_id = "aurora.txt"
    adapter_version = "1.0"
    source_format = "txt"
    capabilities = AdapterCapabilities(
        extensions=(".txt",),
        media_types=("text/plain",),
        unit_kinds=("TEXT_BLOCK",),
        supports_partial_results=False,
        supports_native_extraction=True,
        supports_ocr_fallback=False,
    )

    def extract(self, source: BinaryIO, context: ExtractionContext):
        data = read_bounded(source, context.limits.maximum_file_bytes)
        decoded, replaced = decode_utf8(data)
        lines = decoded.splitlines()
        units: list[ContentUnitDraft] = []
        block: list[str] = []
        block_start = 1

        def emit(end_line: int) -> None:
            nonlocal block
            raw = "\n".join(block)
            text = normalized_text(raw)
            if text:
                for part, character_start, character_end in _bounded_parts(
                    text, context.limits.maximum_field_characters
                ):
                    units.append(
                        ContentUnitDraft(
                            ordinal=len(units),
                            kind="TEXT_BLOCK",
                            text=part,
                            locator={
                                "v": 1,
                                "type": "text_range",
                                "line_start": block_start,
                                "line_end": end_line,
                                "character_start": character_start,
                                "character_end": character_end,
                            },
                            extraction_method="NATIVE",
                            content_type="text/plain",
                        )
                    )
            block = []

        for line_number, line in enumerate(lines, start=1):
            if line.strip():
                if not block:
                    block_start = line_number
                block.append(line)
            elif block:
                emit(line_number - 1)
        if block:
            emit(len(lines))

        warnings = ["INVALID_UTF8_REPLACED"] if replaced else []
        return finalize_document(
            source_format=self.source_format,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            units=units,
            limits=context.limits,
            warnings=warnings,
            diagnostics={
                "line_count": len(lines),
                "encoding": "utf-8",
                "invalid_unicode_replaced": replaced,
            },
        )


class MarkdownAdapter:
    adapter_id = "aurora.markdown"
    adapter_version = "1.0"
    source_format = "markdown"
    capabilities = AdapterCapabilities(
        extensions=(".md", ".markdown"),
        media_types=("text/markdown", "text/x-markdown", "text/plain"),
        unit_kinds=("MARKDOWN_SECTION",),
        supports_partial_results=False,
        supports_native_extraction=True,
        supports_ocr_fallback=False,
    )

    def extract(self, source: BinaryIO, context: ExtractionContext):
        data = read_bounded(source, context.limits.maximum_file_bytes)
        decoded, replaced = decode_utf8(data)
        lines = decoded.splitlines()
        sections: list[dict] = []
        current = {
            "heading": None,
            "level": 0,
            "path": [],
            "start": 1,
            "lines": [],
            "parent_section": None,
        }
        heading_path: list[str] = []
        heading_sections: dict[int, int] = {}
        in_fence = False

        def finish(end_line: int) -> None:
            if current["heading"] is not None or any(
                str(value).strip() for value in current["lines"]
            ):
                current["end"] = end_line
                sections.append(dict(current))

        for line_number, line in enumerate(lines, start=1):
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
            match = None if in_fence else HEADING.match(line)
            if match:
                finish(line_number - 1)
                level = len(match.group(1))
                title = match.group(2).strip()
                heading_path = heading_path[: level - 1]
                heading_path.append(title)
                parent_section = next(
                    (
                        heading_sections[parent_level]
                        for parent_level in range(level - 1, 0, -1)
                        if parent_level in heading_sections
                    ),
                    None,
                )
                heading_sections = {
                    key: value for key, value in heading_sections.items() if key < level
                }
                current = {
                    "heading": title,
                    "level": level,
                    "path": list(heading_path),
                    "start": line_number,
                    "lines": [title],
                    "parent_section": parent_section,
                }
                heading_sections[level] = len(sections)
            else:
                current["lines"].append(line)
        finish(len(lines))

        units: list[ContentUnitDraft] = []
        section_first_ordinal: dict[int, int] = {}
        for section_index, section in enumerate(sections):
            raw_section = "\n".join(section["lines"])
            text = normalized_text(HTML_COMMENT.sub("", raw_section))
            if not text or not any(character.isalnum() for character in text):
                continue
            section_first_ordinal[section_index] = len(units)
            parent_section = section["parent_section"]
            parent_ordinal = (
                section_first_ordinal.get(parent_section)
                if isinstance(parent_section, int)
                else None
            )
            for part, character_start, character_end in _bounded_parts(
                text, context.limits.maximum_field_characters
            ):
                units.append(
                    ContentUnitDraft(
                        ordinal=len(units),
                        kind="MARKDOWN_SECTION",
                        text=part,
                        locator={
                            "v": 1,
                            "type": "markdown_section",
                            "heading_path": section["path"],
                            "line_start": section["start"],
                            "line_end": section["end"],
                            "character_start": character_start,
                            "character_end": character_end,
                        },
                        extraction_method="NATIVE",
                        content_type="text/markdown",
                        parent_ordinal=parent_ordinal,
                        metadata={
                            "heading": section["heading"],
                            "heading_level": section["level"],
                            "contains_code_fence": "```" in raw_section or "~~~" in raw_section,
                            "link_count": len(LINK.findall(raw_section)),
                        },
                    )
                )

        warnings = ["INVALID_UTF8_REPLACED"] if replaced else []
        return finalize_document(
            source_format=self.source_format,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            units=units,
            limits=context.limits,
            warnings=warnings,
            diagnostics={
                "line_count": len(lines),
                "section_count": len(sections),
                "encoding": "utf-8",
                "invalid_unicode_replaced": replaced,
            },
        )
