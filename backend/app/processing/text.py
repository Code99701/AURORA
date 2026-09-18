import re


CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HORIZONTAL_WHITESPACE = re.compile(r"[\t \u00a0]+")


def clean_extracted_text(text: str | None) -> str:
    """Normalize extraction artifacts without rewriting source meaning.

    Single line breaks inside a paragraph become spaces, while one blank line
    continues to separate paragraphs. Page boundaries are handled by callers.
    """
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = CONTROL_CHARACTERS.sub("", normalized)

    paragraphs: list[str] = []
    current_lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = HORIZONTAL_WHITESPACE.sub(" ", raw_line).strip()
        if line:
            current_lines.append(line)
        elif current_lines:
            paragraphs.append(" ".join(current_lines))
            current_lines = []
    if current_lines:
        paragraphs.append(" ".join(current_lines))
    return "\n\n".join(paragraphs).strip()
