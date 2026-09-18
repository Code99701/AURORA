from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    text: str
    page_chunk_index: int
    character_count: int
    approximate_token_count: int


def _preferred_boundary(text: str, start: int, hard_end: int) -> int:
    """Choose a stable boundary near the hard limit without creating tiny chunks."""
    if hard_end >= len(text):
        return len(text)
    lower_bound = start + int((hard_end - start) * 0.8)
    for marker in ("\n\n", ". ", "? ", "! ", "\n", " "):
        position = text.rfind(marker, lower_bound, hard_end)
        if position >= lower_bound:
            return position + len(marker.rstrip())
    return hard_end


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    """Split cleaned page text deterministically using bounded character windows.

    Pages are never mixed, which keeps every chunk's page provenance exact. A
    character estimate (ceil(chars / 4)) is stored as metadata; it is explicitly
    not presented as the embedding provider's tokenizer count.
    """
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap smaller than chunk_size")

    source = text.strip()
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
        while next_start < end and source[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks
