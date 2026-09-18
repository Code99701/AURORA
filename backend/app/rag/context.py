from dataclasses import dataclass
from html import escape
import json

from app.services.retrieval import RetrievedChunk


@dataclass(frozen=True)
class BuiltContext:
    text: str
    evidence: tuple[RetrievedChunk, ...]
    character_count: int


def _evidence_block(evidence: RetrievedChunk, number: int, content: str) -> str:
    locator = json.dumps(
        evidence.locator, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ) if evidence.locator is not None else "null"
    return (
        f'<EVIDENCE number="{number}">\n'
        f"chunk_id: {evidence.chunk_id}\n"
        f"document_id: {evidence.document_id}\n"
        f"filename: {escape(evidence.filename)}\n"
        f"page_number: {evidence.page_number}\n"
        f"locator: {escape(locator)}\n"
        f"extraction_method: {escape(evidence.extraction_method or 'unknown')}\n"
        f"similarity: {evidence.similarity:.6f}\n"
        "<UNTRUSTED_DOCUMENT_TEXT>\n"
        f"{escape(content)}\n"
        "</UNTRUSTED_DOCUMENT_TEXT>\n"
        "</EVIDENCE>"
    )


def build_context(
    evidence: list[RetrievedChunk], max_characters: int
) -> BuiltContext:
    """Build bounded context from already-authorized, relevance-ordered evidence."""
    blocks: list[str] = []
    selected: list[RetrievedChunk] = []
    used = 0
    separator = "\n\n"
    for item in evidence:
        empty_block = _evidence_block(item, len(selected) + 1, " [TRUNCATED]")
        separator_length = len(separator) if blocks else 0
        available = max_characters - used - separator_length
        if available <= len(empty_block):
            break
        full_block = _evidence_block(item, len(selected) + 1, item.text)
        if len(full_block) <= available:
            block = full_block
        else:
            # Escaping may expand characters, so shrink until the final serialized
            # evidence block fits the deterministic budget.
            content_limit = min(len(item.text), available - len(empty_block))
            while content_limit > 0:
                block = _evidence_block(
                    item,
                    len(selected) + 1,
                    item.text[:content_limit].rstrip() + " [TRUNCATED]",
                )
                if len(block) <= available:
                    break
                content_limit -= 1
            else:
                break
        blocks.append(block)
        selected.append(item)
        used += separator_length + len(block)
        if used >= max_characters:
            break
    result = separator.join(blocks)
    return BuiltContext(result, tuple(selected), len(result))
