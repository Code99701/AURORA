from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import BinaryIO
from zipfile import BadZipFile, ZipFile


@dataclass(frozen=True)
class FormatSpec:
    source_format: str
    extensions: tuple[str, ...]
    media_types: tuple[str, ...]
    canonical_media_type: str
    container: str
    required_member: str | None = None


FORMAT_SPECS = (
    FormatSpec(
        "pdf", (".pdf",), ("application/pdf", "application/x-pdf"),
        "application/pdf", "pdf",
    ),
    FormatSpec("txt", (".txt",), ("text/plain",), "text/plain", "text"),
    FormatSpec(
        "markdown", (".md", ".markdown"),
        ("text/markdown", "text/x-markdown", "text/plain"),
        "text/markdown", "text",
    ),
    FormatSpec(
        "csv", (".csv",), ("text/csv", "application/csv", "text/plain"),
        "text/csv", "text",
    ),
    FormatSpec(
        "tsv", (".tsv",),
        ("text/tab-separated-values", "text/tsv", "text/plain"),
        "text/tab-separated-values", "text",
    ),
    FormatSpec(
        "docx", (".docx",),
        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "ooxml", "word/document.xml",
    ),
    FormatSpec(
        "xlsx", (".xlsx",),
        ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "ooxml", "xl/workbook.xml",
    ),
    FormatSpec(
        "pptx", (".pptx",),
        ("application/vnd.openxmlformats-officedocument.presentationml.presentation",),
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ooxml", "ppt/presentation.xml",
    ),
)


def format_spec_for(filename: str, declared_media_type: str) -> FormatSpec | None:
    extension = PurePosixPath(filename).suffix.casefold()
    declared = declared_media_type.casefold()
    matches = [
        spec
        for spec in FORMAT_SPECS
        if extension in spec.extensions and declared in spec.media_types
    ]
    return matches[0] if len(matches) == 1 else None


def inspect_ooxml_archive(
    source: BinaryIO,
    *,
    required_member: str,
    maximum_entries: int,
    maximum_uncompressed_bytes: int,
) -> dict[str, int]:
    try:
        source.seek(0)
        with ZipFile(source) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > maximum_entries:
                raise ValueError("archive entry limit")
            names: set[str] = set()
            uncompressed = 0
            compressed = 0
            for entry in entries:
                path = PurePosixPath(entry.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or entry.flag_bits & 0x1:
                    raise ValueError("unsafe archive member")
                names.add(path.as_posix())
                uncompressed += entry.file_size
                compressed += entry.compress_size
                if uncompressed > maximum_uncompressed_bytes:
                    raise ValueError("archive expansion limit")
            if "[Content_Types].xml" not in names or required_member not in names:
                raise ValueError("container type mismatch")
            if any(name.casefold().endswith("vbaproject.bin") for name in names):
                raise ValueError("active content is not supported")
            # Office XML must remain inert data. Reject DTD/entity declarations
            # before any document parser sees the package.
            for entry in entries:
                normalized_name = entry.filename.casefold()
                if normalized_name.endswith((".xml", ".rels")):
                    with archive.open(entry) as xml_part:
                        prefix = xml_part.read(8192).upper()
                    if b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
                        raise ValueError("active XML declarations are not supported")
            # A very high aggregate expansion ratio is rejected even below the
            # absolute uncompressed-byte ceiling.
            if compressed and uncompressed > max(10_000_000, compressed * 250):
                raise ValueError("suspicious archive expansion ratio")
            return {
                "archive_entry_count": len(entries),
                "archive_uncompressed_bytes": uncompressed,
            }
    except (BadZipFile, OSError, ValueError) as exc:
        raise ValueError("Invalid or unsafe Office Open XML container") from exc
    finally:
        source.seek(0)


def validate_signature(
    source: BinaryIO,
    spec: FormatSpec,
    *,
    maximum_archive_entries: int,
    maximum_archive_uncompressed_bytes: int,
) -> None:
    source.seek(0)
    prefix = source.read(8192)
    source.seek(0)
    if spec.container == "pdf":
        if not prefix.startswith(b"%PDF-"):
            raise ValueError("File content does not match the PDF format")
        return
    if spec.container == "text":
        if not prefix or b"\x00" in prefix:
            raise ValueError("File content is not supported UTF-8 text")
        decoded = prefix.decode("utf-8-sig", errors="replace")
        controls = sum(
            ord(character) < 32 and character not in "\t\r\n"
            for character in decoded
        )
        if decoded and controls / len(decoded) > 0.05:
            raise ValueError("File content is not supported UTF-8 text")
        return
    if spec.container == "ooxml" and spec.required_member:
        inspect_ooxml_archive(
            source,
            required_member=spec.required_member,
            maximum_entries=maximum_archive_entries,
            maximum_uncompressed_bytes=maximum_archive_uncompressed_bytes,
        )
        return
    raise ValueError("Unsupported document format")
