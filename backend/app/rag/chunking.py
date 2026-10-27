"""Structure-aware chunking engine for AURORA RAG pipeline.

Supports:
- Consecutive slide / small page merging to ~800-1000 characters
- Tracking page_start and page_end with backward-compatible page_number
- Keeping headings with their body text (no orphaned headings)
- Table-safe splitting: never split across a table row
- Noise chunk suppression: filters out pure noise like "CONTD.. 9"
- Contextual prefix: "Document | Section | Pages" embedded into vector but omitted from citations
- Unicode private-use glyph stripping (U+E000 to U+F8FF)
"""

from dataclasses import dataclass
import re
from typing import Any
import uuid


PRIVATE_USE_PATTERN = re.compile(r"[\uE000-\uF8FF]")
NOISE_PATTERNS = [
    re.compile(r"^\s*contd\.*\s*\d*\s*$", re.IGNORECASE),

    re.compile(r"^\s*unit[-_\s]*[ivxlcdm0-9]+\s*(ann)?\s*(slide)?\s*\d*\s*$", re.IGNORECASE),
    re.compile(r"^\s*slide\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"^\s*page\s+\d+\s+(of\s+\d+)?\s*$", re.IGNORECASE),
]
TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
HEADING_LINE_PATTERN = re.compile(
    r"^(#{1,6}\s+.+|[A-Z0-9][A-Z0-9\s,:–-]{2,60}:?$|Chapter\s+\d+|Section\s+\d+|Topics\s*:)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextChunk:
    """Legacy chunk representation for backward compatibility."""
    text: str
    page_chunk_index: int
    character_count: int
    approximate_token_count: int
    page_start: int | None = None
    page_end: int | None = None
    context_prefix: str | None = None
    embedded_text: str | None = None
    parent_chunk_id: uuid.UUID | None = None


@dataclass(frozen=True)
class StructuredChunk:
    """Structure-aware chunk with clean text, embedded text, and page ranges."""
    text: str                      # Clean text for display and citations
    embedded_text: str             # Contextual prefix + clean text for embedding
    context_prefix: str            # "Document: <file> | Section: <heading> | Pages: <a-b>"
    page_start: int | None
    page_end: int | None
    page_number: int | None        # Backward compatible: equals page_start
    chunk_index: int
    page_chunk_index: int
    character_count: int
    approximate_token_count: int
    parent_chunk_id: uuid.UUID | None = None
    extracted_page_id: int | None = None
    content_unit_id: uuid.UUID | None = None


def strip_private_use_glyphs(text: str) -> str:
    """Strip private-use area Unicode glyphs (U+E000 to U+F8FF) and clean artifacts."""
    if not text:
        return ""
    cleaned = PRIVATE_USE_PATTERN.sub("", text)
    # Remove null bytes or non-printable controls
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    return cleaned


def is_noise_text(text: str) -> bool:
    """Detect whether a text fragment is pure boilerplate or noise."""
    stripped = text.strip()
    if not stripped:
        return True
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return True
    return all(any(p.match(line) for p in NOISE_PATTERNS) for line in lines)


def is_table_row(line: str) -> bool:
    """Detect if a line is part of a markdown or delimited table."""
    s = line.strip()
    return bool(TABLE_ROW_PATTERN.match(s)) or ("\t" in s and s.count("\t") >= 2)


def is_heading(line: str) -> bool:
    """Check if a line looks like a title or section heading."""
    s = line.strip()
    if not s or len(s) > 80:
        return False
    if s.startswith("#"):
        return True
    if s.endswith(":") and len(s) < 50:
        return True
    # Uppercase or titlecase short heading
    if s.isupper() and len(s) >= 4:
        return True
    return bool(HEADING_LINE_PATTERN.match(s))


def extract_heading_from_text(text: str) -> str | None:
    """Extract the first meaningful heading from a text block."""
    for line in text.splitlines():
        line = line.strip()
        if not line or is_noise_text(line):
            continue
        if is_heading(line):
            cleaned = line.lstrip("#").strip().rstrip(":")
            # Filter out slide numbers in heading
            cleaned = re.sub(r"\s+\d+$", "", cleaned)
            if len(cleaned) >= 3:
                return cleaned[:60]
    return None


def _preferred_boundary(text: str, start: int, hard_end: int) -> int:
    """Choose a stable boundary near the hard limit without splitting table rows or orphaned headings."""
    if hard_end >= len(text):
        return len(text)

    # 1. Check if hard_end lands inside a table row in text
    line_start = text.rfind("\n", 0, hard_end)
    line_start = 0 if line_start == -1 else line_start + 1
    line_end = text.find("\n", hard_end)
    line_end = len(text) if line_end == -1 else line_end
    current_line = text[line_start:line_end].strip()

    if is_table_row(current_line):
        # We are inside a table row. Either break after this line or before this line
        if line_end - start <= int((hard_end - start) * 1.5):
            return min(len(text), line_end + 1)
        elif line_start > start + int((hard_end - start) * 0.4):
            return line_start

    # 2. Standard punctuation boundaries
    lower_bound = start + int((hard_end - start) * 0.75)
    for marker in ("\n\n", ". ", "? ", "! ", "\n", "; ", ", ", " "):
        position = text.rfind(marker, lower_bound, hard_end)
        if position >= lower_bound:
            candidate = position + len(marker.rstrip())
            # Check if candidate falls inside a table row
            c_line_start = text.rfind("\n", 0, candidate)
            c_line_start = 0 if c_line_start == -1 else c_line_start + 1
            c_line_end = text.find("\n", candidate)
            c_line_end = len(text) if c_line_end == -1 else c_line_end
            if is_table_row(text[c_line_start:c_line_end].strip()):
                if c_line_start > lower_bound:
                    candidate = c_line_start
                elif c_line_end + 1 <= len(text) and c_line_end + 1 - start <= int((hard_end - start) * 1.5):
                    candidate = c_line_end + 1

            # Check if candidate falls right after a heading line (orphaned heading)
            preceding_line = text[start:candidate].splitlines()[-1].strip() if text[start:candidate].splitlines() else ""
            if is_heading(preceding_line) and candidate < len(text):
                heading_start = text[start:candidate].rfind(preceding_line)
                if heading_start > lower_bound:
                    return start + heading_start
            return candidate

    return hard_end


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    """Split cleaned page text deterministically using bounded character windows.

    Backward-compatible function preserving existing tests.
    """
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap smaller than chunk_size")

    source = strip_private_use_glyphs(text).strip()
    if not source:
        return []

    chunks: list[TextChunk] = []
    start = 0
    while start < len(source):
        hard_end = min(start + chunk_size, len(source))
        end = _preferred_boundary(source, start, hard_end)
        value = source[start:end].strip()
        if value:
            chunks.append(
                TextChunk(
                    text=value,
                    page_chunk_index=len(chunks),
                    character_count=len(value),
                    approximate_token_count=max(1, (len(value) + 3) // 4),
                )
            )
        if end >= len(source):
            break
        next_start = max(end - overlap, start + 1)
        # Avoid starting next chunk in the middle of a table row
        line_start = source.rfind("\n", 0, next_start)
        line_start = 0 if line_start == -1 else line_start + 1
        line_end = source.find("\n", next_start)
        line_end = len(source) if line_end == -1 else line_end
        if is_table_row(source[line_start:line_end].strip()):
            if next_start > line_start:
                next_start = min(len(source), line_end + 1)
        while next_start < end and source[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks


def build_context_prefix(
    filename: str,
    section: str | None,
    page_start: int | None,
    page_end: int | None,
) -> str:
    """Format contextual prefix: 'Document: <file> | Section: <sec> | Pages: <start>-<end>'."""
    sec_str = section.strip() if section and section.strip() else "Overview"
    if page_start is not None and page_end is not None:
        pages_str = f"{page_start}" if page_start == page_end else f"{page_start}-{page_end}"
    elif page_start is not None:
        pages_str = f"{page_start}"
    else:
        pages_str = "N/A"
    return f"Document: {filename} | Section: {sec_str} | Pages: {pages_str}"


def chunk_document_sources(
    sources: list[Any],
    document_filename: str,
    target_chunk_size: int = 900,
    overlap: int = 120,
    min_chunk_size: int = 40,
) -> list[StructuredChunk]:
    """Structure-aware chunker over document sources (ExtractedPages or ContentUnits).

    Rules applied:
    - Merges consecutive small slides/pages to ~800-1000 chars
    - Stores page_start and page_end
    - Drops pure noise chunks (e.g. 'CONTD.. 9')
    - Keeps headings with their body
    - Never splits across a table row
    - Contextual prefix generated and added to embedded_text only
    - Unicode private-use glyphs stripped
    """
    if not sources:
        return []

    cleaned_sources = []
    for s in sources:
        raw_text = getattr(s, "text", "") or ""
        cleaned = strip_private_use_glyphs(raw_text).strip()

        extracted_page_id = None
        content_unit_id = None
        if hasattr(s, "extracted_page") and hasattr(s, "content_unit"):
            # IndexableSource wrapper
            extracted_page_id = s.extracted_page.id if s.extracted_page is not None else None
            content_unit_id = s.content_unit.id if s.content_unit is not None else None
            page_num = s.page_number
        elif hasattr(s, "page_number") and hasattr(s, "document_id") and not hasattr(s, "kind"):
            # Raw ExtractedPage model
            extracted_page_id = getattr(s, "id", None)
            page_num = getattr(s, "page_number", None)
        elif hasattr(s, "kind") or hasattr(s, "locator"):
            # Raw ContentUnit model
            content_unit_id = getattr(s, "id", None)
            page_num = getattr(s, "page_number", None)
        else:
            page_num = getattr(s, "page_number", None)
            extracted_page_id = getattr(s, "extracted_page_id", None)
            content_unit_id = getattr(s, "content_unit_id", None)

        is_noise = is_noise_text(cleaned)
        cleaned_sources.append({
            "source": s,
            "text": cleaned,
            "page_number": page_num,
            "extracted_page_id": extracted_page_id,
            "content_unit_id": content_unit_id,
            "heading": extract_heading_from_text(cleaned),
            "is_noise": is_noise,
        })

    # Fallback: if all non-empty sources are flagged as noise, keep them
    has_real_content = any(cs["text"] and not cs["is_noise"] for cs in cleaned_sources)
    if not has_real_content:
        for cs in cleaned_sources:
            if cs["text"]:
                cs["is_noise"] = False

    chunks: list[StructuredChunk] = []
    per_unit_chunk_count: dict[uuid.UUID, int] = {}
    per_page_chunk_count: dict[int, int] = {}

    accum_texts: list[str] = []
    accum_page_start: int | None = None
    accum_page_end: int | None = None
    accum_heading: str | None = None
    accum_extracted_page_id: int | None = None
    accum_content_unit_id: uuid.UUID | None = None

    def get_next_page_chunk_index(unit_id: uuid.UUID | None, page_id: int | None) -> int:
        if unit_id is not None:
            idx = per_unit_chunk_count.get(unit_id, 0)
            per_unit_chunk_count[unit_id] = idx + 1
            return idx
        if page_id is not None:
            idx = per_page_chunk_count.get(page_id, 0)
            per_page_chunk_count[page_id] = idx + 1
            return idx
        return 0

    def flush_accumulator() -> None:
        nonlocal accum_texts, accum_page_start, accum_page_end, accum_heading
        nonlocal accum_extracted_page_id, accum_content_unit_id
        if not accum_texts:
            return
        combined_text = "\n\n".join(t for t in accum_texts if t.strip()).strip()
        if combined_text:
            ctx_prefix = build_context_prefix(
                document_filename,
                accum_heading,
                accum_page_start,
                accum_page_end,
            )
            embedded_text = f"{ctx_prefix}\n\n{combined_text}"
            p_chunk_idx = get_next_page_chunk_index(accum_content_unit_id, accum_extracted_page_id)
            chunks.append(
                StructuredChunk(
                    text=combined_text,
                    embedded_text=embedded_text,
                    context_prefix=ctx_prefix,
                    page_start=accum_page_start,
                    page_end=accum_page_end,
                    page_number=accum_page_start,
                    chunk_index=len(chunks),
                    page_chunk_index=p_chunk_idx,
                    character_count=len(combined_text),
                    approximate_token_count=max(1, (len(combined_text) + 3) // 4),
                    extracted_page_id=accum_extracted_page_id,
                    content_unit_id=accum_content_unit_id,
                )
            )
        accum_texts = []
        accum_page_start = None
        accum_page_end = None
        accum_heading = None
        accum_extracted_page_id = None
        accum_content_unit_id = None

    active_section = "Overview"

    for cs in cleaned_sources:
        text = cs["text"]
        page_num = cs["page_number"]
        heading = cs["heading"]

        if heading:
            active_section = heading

        # Drop pure noise chunks
        if cs["is_noise"] or not text:
            continue

        # If individual page is large (e.g. dense prose > 750 chars)
        if len(text) > 750:
            flush_accumulator()
            # Split the large page using boundary-safe chunking
            page_chunks = chunk_text(text, chunk_size=target_chunk_size, overlap=overlap)
            for pc in page_chunks:
                ctx_prefix = build_context_prefix(
                    document_filename,
                    active_section,
                    page_num,
                    page_num,
                )
                embedded_text = f"{ctx_prefix}\n\n{pc.text}"
                p_chunk_idx = get_next_page_chunk_index(cs["content_unit_id"], cs["extracted_page_id"])
                chunks.append(
                    StructuredChunk(
                        text=pc.text,
                        embedded_text=embedded_text,
                        context_prefix=ctx_prefix,
                        page_start=page_num,
                        page_end=page_num,
                        page_number=page_num,
                        chunk_index=len(chunks),
                        page_chunk_index=p_chunk_idx,
                        character_count=len(pc.text),
                        approximate_token_count=pc.approximate_token_count,
                        extracted_page_id=cs["extracted_page_id"],
                        content_unit_id=cs["content_unit_id"],
                    )
                )
            continue

        # Small page / slide: accumulate
        current_len = sum(len(t) for t in accum_texts)
        if accum_texts and (current_len + len(text) > target_chunk_size):
            flush_accumulator()

        if not accum_texts:
            accum_page_start = page_num
            accum_extracted_page_id = cs["extracted_page_id"]
            accum_content_unit_id = cs["content_unit_id"]
            accum_heading = active_section

        accum_texts.append(text)
        accum_page_end = page_num or accum_page_start
        if heading:
            accum_heading = heading

    flush_accumulator()
    return chunks

