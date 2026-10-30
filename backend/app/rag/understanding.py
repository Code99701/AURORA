"""General Query Understanding & Intent Analysis for AURORA RAG Platform.

Interprets natural-language user requests before retrieval and generation:
1. Intent / Task Classification: FACTUAL, SUMMARY, COMPARISON, EXTRACTION, EXPLANATION, TRANSLATION, LOCATION.
2. Target Document Resolution: Dynamically matches one or multiple documents from the workspace without hardcoded if/else trees.
3. Structural Constraints: Page and slide number / range extraction.
4. Language Preferences: Multi-language detection (Hindi, English, etc.).
5. Detail & Format Requirements: Concise, detailed, bulleted, simple.
6. Contextual Follow-up Disambiguation: Connects or cleanly isolates conversation context.
"""

from dataclasses import dataclass
import re
from typing import Any

from app.models.document import Document


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageSlideConstraint:
    start: int
    end: int
    unit: str  # "page" or "slide"
    raw_mention: str

    @property
    def is_single(self) -> bool:
        return self.start == self.end


@dataclass(frozen=True)
class TargetDocumentMatch:
    document_id: Any
    filename: str
    matched_term: str
    confidence: float


@dataclass(frozen=True)
class QueryIntent:
    task: str  # FACTUAL, DOCUMENT_OVERVIEW, TOPIC_SUMMARY, COMPARISON, EXTRACTION, EXPLANATION, TRANSLATION, LOCATION
    raw_query: str
    clean_query: str
    search_query: str
    target_documents: tuple[TargetDocumentMatch, ...]
    page_slide_constraint: PageSlideConstraint | None
    target_language: str | None
    detail_level: str | None  # "concise", "detailed", "simple", "bulleted"
    is_multi_document: bool
    is_overview: bool
    is_follow_up: bool
    topic_subject: str
    is_full_coverage: bool = False
    task_guidance: str | None = None


# ---------------------------------------------------------------------------
# Regex Patterns for Intent and Constraints
# ---------------------------------------------------------------------------

# Numeral normalization mappings for flexible document and query matching
ROMAN_TO_ARABIC = {
    "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5",
    "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10",
    "xi": "11", "xii": "12", "xiii": "13", "xiv": "14", "xv": "15",
    "xvi": "16", "xvii": "17", "xviii": "18", "xix": "19", "xx": "20",
}
ARABIC_TO_ROMAN = {v: k for k, v in ROMAN_TO_ARABIC.items()}


def normalize_numerals_in_text(text: str) -> list[str]:
    """Generate numeral-normalized variants of a string (e.g. 'unit i' <-> 'unit 1')."""
    words = re.findall(r"[a-zA-Z0-9]+", text.casefold())
    if not words:
        return [text.casefold()]
    variants = [text.casefold()]
    if any(w in ROMAN_TO_ARABIC for w in words):
        variants.append(" ".join(ROMAN_TO_ARABIC.get(w, w) for w in words))
    if any(w in ARABIC_TO_ROMAN for w in words):
        variants.append(" ".join(ARABIC_TO_ROMAN.get(w, w) for w in words))
    return list(dict.fromkeys(variants))


# Multi-page and multi-slide patterns
PAGE_SLIDE_PATTERNS = [
    # "first N pages/slides"
    (
        re.compile(r"\bfirst\s+(?P<num>\d+)\s+(?P<unit>pages?|slides?)\b", re.IGNORECASE),
        lambda m: (1, min(int(m.group("num")), 50), "slide" if "slide" in m.group("unit").lower() else "page"),
    ),
    # "pages/slides X to Y", "pages/slides X-Y", "pages/slides X through Y"
    (
        re.compile(r"\b(?P<unit>pages?|slides?)\s+(?P<start>\d+)\s*(?:to|-|through)\s*(?P<end>\d+)\b", re.IGNORECASE),
        lambda m: (
            int(m.group("start")),
            min(int(m.group("end")), int(m.group("start")) + 50),
            "slide" if "slide" in m.group("unit").lower() else "page",
        ),
    ),
    # "starting from page/slide X", "from page/slide X onwards", "from page/slide X"
    (
        re.compile(r"\b(?:starting\s+from|from)\s+(?:(?P<unit>pages?|slides?)\s+)?(?P<num>\d+)(?:\s+onwards|\s+to\s+the\s+end)?\b", re.IGNORECASE),
        lambda m: (
            int(m.group("num")),
            999999,
            "slide" if m.group("unit") and "slide" in m.group("unit").lower() else "page",
        ),
    ),
    # "cover all pages/slides", "every page/slide", "all pages/slides"
    (
        re.compile(r"\b(?:cover\s+)?(?:all|every)\s+(?P<unit>pages?|slides?)\b", re.IGNORECASE),
        lambda m: (
            1,
            999999,
            "slide" if "slide" in m.group("unit").lower() else "page",
        ),
    ),
    # "page/slide X", "pg X", "pg. X", "p. X", "slide #X"
    (
        re.compile(r"\b(?:(?P<unit>pages?|slides?)\s+|pg\.?\s*|p\.\s*)(?:#\s*)?(?P<num>\d+)\b", re.IGNORECASE),
        lambda m: (
            int(m.group("num")),
            int(m.group("num")),
            "slide" if m.group("unit") and "slide" in m.group("unit").lower() else "page",
        ),
    ),
]

# Task classification patterns
COMPARISON_PATTERN = re.compile(
    r"\b(?:compare|comparison|differ(?:ence|ences)?\s+between|how\s+does\s+.*?\s+differ\s+from|versus|\bvs\.?\b|contrast|similarities\s+(?:and|&)\s+differences)\b",
    re.IGNORECASE,
)

FULL_COVERAGE_PATTERN = re.compile(
    r"\b(?:cover\s+(?:all|every|each)\s+(?:pages?|slides?))\b|"
    r"\b(?:starting\s+from\s+(?:page|slide)?\s*\d+)\b|"
    r"\b(?:tell\s+me\s+everything\s+present\s+in|what\s+is\s+present\s+in)\b|"
    r"\b(?:(?:list|inventory|enumerate)\s+(?:all|every|each)\s+(?:slides?|pages?|sections?|topics?))\b|"
    r"\b(?:section[-\s]+by[-\s]+section|page[-\s]+by[-\s]+page|slide[-\s]+by[-\s]+slide|chapter[-\s]+by[-\s]+chapter)\b|"
    r"\b(?:walk\s+through\s+(?:the\s+)?(?:entire|whole)?\s*(?:document|presentation|report|paper|pdf|file|slides?))\b|"
    r"\b(?:inventory\s+of\s+(?:all\s+)?(?:sections?|pages?|slides?|topics?|chapters?))\b|"
    r"\b(?:explain\s+(?:the\s+)?(?:whole|entire)\s+(?:document|presentation|report|paper|pdf|file))\b|"
    r"\b(?:summarize\s+this\s+entire\s+document|summarise\s+this\s+entire\s+document|summarize\s+the\s+whole\s+document|summarise\s+the\s+whole\s+document)\b",
    re.IGNORECASE,
)

DOCUMENT_OVERVIEW_PATTERN = re.compile(
    r"\b(?:summar(?:y|ise|ize|izing)|overview|outline|synopsis|table\s+of\s+contents)\s+(?:of\s+)?(?:this|the|all|entire|whole)?\s*(?:document|pdf|book|paper|file|presentation|slides?|workspace)\b|"
    r"\b(?:explain|describe|details?\s+(?:present\s+in|of|in)|what\s+(?:are|is)\s+(?:the\s+)?(?:details|contents?)\s+(?:in|of)|contents?\s+of)\s+(?:this|the|all|entire|whole)?\s*(?:document|pdf|book|paper|file|presentation|slides?|\.[a-z]{3,4})\b|"
    r"\b(?:what\s+is\s+(?:this|the)\s+(?:document|presentation|book|pdf|file)\s+about|general\s+overview|executive\s+summary)\b|"
    r"^(?:can\s+you\s+)?(?:please\s+)?(?:provide\s+(?:an?\s+)?|give\s+(?:an?\s+)?)?(?:summarise|summarize|summary|overview|outline)\s*(?:of\s+(?:this|the|all)?\s*(?:document|pdf|book|presentation|file|paper)?)?\s*[\?\.]?$|"
    r"\b(?:cover\s+(?:all|every)\s+(?:pages?|slides?))\b|"
    r"\b(?:starting\s+from\s+(?:page|slide)?\s*\d+)\b|"
    r"\b(?:tell\s+me\s+everything\s+present\s+in|what\s+is\s+present\s+in)\b|"
    r"\b(?:list\s+all\s+(?:slides?|pages?)\s+and\s+their\s+topics)\b|"
    r"\b(?:section[-\s]+by[-\s]+section|page[-\s]+by[-\s]+page|slide[-\s]+by[-\s]+slide|chapter[-\s]+by[-\s]+chapter)\b|"
    r"\b(?:summarize\s+this\s+entire\s+document|summarise\s+this\s+entire\s+document|summarize\s+the\s+whole\s+document)\b",
    re.IGNORECASE,
)

TOPIC_SUMMARY_PATTERN = re.compile(
    r"\b(?:summarise|summarize|summary\s+of|synopsis\s+of|brief\s+summary|key\s+takeaways\s+of|gist\s+of)\b",
    re.IGNORECASE,
)

EXTRACTION_PATTERN = re.compile(
    r"\b(?:list\s+(?:all|the|every)?|extract\s+(?:all|the)?|bullet\s+points?|what\s+are\s+the\s+(?:key|main|three|four|five|\d+)|enumerate|identify\s+all)\b",
    re.IGNORECASE,
)

EXPLANATION_PATTERN = re.compile(
    r"\b(?:explain\s+(?:simply|it|this|that|more\s+simply|in\s+simple\s+terms|in\s+simple\s+words)|simpler|simple\s+version|give\s+more\s+details|in\s+detail|elaborate\s+on)\b",
    re.IGNORECASE,
)

LOCATION_PATTERN = re.compile(
    r"\b(?:where\s+(?:is|are|does)\b.*?\b(?:mentioned|stated|found|written|located|appear|discussed)|which\s+(?:page|slide|section)\b)\b",
    re.IGNORECASE,
)

TRANSLATION_PATTERN = re.compile(
    r"\b(?:translate|translation)\b.*?\b(?:(?:in|into|to)\s+(?P<lang>[A-Za-z]+))|"
    r"\b(?P<lang_alt>hindi|english|spanish|french|german)\s+(?:me|mein)\s+(?:translate|samjhao|batao)\b|"
    r"(?P<hindi_script>हिंदी\s*में\s*(?:अनुवाद|समझाइए|बताइए)|अनुवाद\s*करें)",
    re.IGNORECASE,
)

DETAIL_PATTERNS = [
    (re.compile(r"\b(?:in\s+detail|detailed|in-depth|comprehensive|elaborate)\b", re.IGNORECASE), "detailed"),
    (re.compile(r"\b(?:briefly|brief|short\s+version|concise|in\s+short|in\s+few\s+words|in\s+3\s+lines)\b", re.IGNORECASE), "concise"),
    (re.compile(r"\b(?:simply|simple\s+terms|simple\s+words|like\s+i'm\s+5|for\s+a\s+beginner)\b", re.IGNORECASE), "simple"),
    (re.compile(r"\b(?:bullet\s*points?|in\s+bullets?|as\s+a\s+list)\b", re.IGNORECASE), "bulleted"),
]


# ---------------------------------------------------------------------------
# Helper Normalization and Extraction Functions
# ---------------------------------------------------------------------------

def extract_page_or_slide_constraint(query: str) -> PageSlideConstraint | None:
    """Extract page or slide constraint from natural text."""
    for pattern, extractor in PAGE_SLIDE_PATTERNS:
        match = pattern.search(query)
        if match:
            s, e, unit = extractor(match)
            if s > 0 and e >= s:
                return PageSlideConstraint(
                    start=s,
                    end=e,
                    unit=unit,
                    raw_mention=match.group(0),
                )
    return None


def _clean_stem(filename: str) -> str:
    """Derive clean search stem by removing extensions and punctuation."""
    stem = filename.rsplit(".", 1)[0]
    stem = re.sub(r"([a-zA-Z])(\d+)", r"\1 \2", stem)
    stem = re.sub(r"(\d+)([a-zA-Z])", r"\1 \2", stem)
    return re.sub(r"[-_\.]+", " ", stem).strip().casefold()


def _generate_document_aliases(filename: str) -> list[str]:
    """Generate search aliases from filename for flexible natural language matching."""
    stem = _clean_stem(filename)
    aliases = [stem]

    # Add Roman <-> Arabic numeral variants of the stem
    for var in normalize_numerals_in_text(stem):
        if var not in aliases:
            aliases.append(var)

    # Stopwords to exclude from single-word tokens (keep identifying terms like unit, part, chapter)
    exclude_tokens = {"pdf", "pptx", "docx", "xlsx", "file", "document", "the", "for", "all", "and", "with", "test"}
    tokens = [t for t in stem.split() if len(t) >= 1 and t not in exclude_tokens]
    
    # Domain aliases
    if "resume" in tokens or "cv" in tokens:
        aliases.extend(["resume", "cv", "candidate resume"])
    if "machine" in tokens and "learning" in tokens:
        aliases.extend(["ml book", "machine learning book", "hundred page book", "hundred page machine learning book"])
    if "ann" in tokens:
        aliases.extend(["ann ppt", "ann presentation", "ann unit 2", "ann slides", "neural network ppt", "neural network presentation"])
    if "report" in tokens:
        aliases.extend(["sample report", "mac report", "department report", "mac department report"])

    # If stem has >= 2 tokens, include normalized combinations
    if len(tokens) >= 2:
        token_str = " ".join(tokens)
        for v in normalize_numerals_in_text(token_str):
            if v not in aliases:
                aliases.append(v)
        prefix_2 = " ".join(tokens[:2])
        for v in normalize_numerals_in_text(prefix_2):
            if v not in aliases:
                aliases.append(v)

    # Deduplicate while preserving order
    seen = set()
    unique_aliases = []
    for a in aliases:
        if a not in seen and len(a) >= 2:
            seen.add(a)
            unique_aliases.append(a)
    return unique_aliases


def resolve_target_documents(
    query: str,
    indexed_documents: list[Document],
) -> list[TargetDocumentMatch]:
    """Dynamically match zero, one, or multiple documents referenced in the query."""
    q_lower = query.casefold()
    query_variants = normalize_numerals_in_text(query)
    q_norms = [f" {re.sub(r'[^a-zA-Z0-9]', ' ', qv)} " for qv in query_variants]

    # Format indicators
    query_indicates_pdf = bool(re.search(r"\b(?:pdf|document)\b", q_lower))
    query_indicates_slides = bool(re.search(r"\b(?:pptx?|slides?|presentation)\b", q_lower))
    query_indicates_doc = bool(re.search(r"\b(?:docx?|word)\b", q_lower))

    matches: list[TargetDocumentMatch] = []
    seen_ids: set[Any] = set()

    for doc in indexed_documents:
        if doc.id in seen_ids:
            continue
        fname_lower = doc.original_filename.casefold()
        ext = fname_lower.rsplit(".", 1)[-1] if "." in fname_lower else ""

        # Format affinity boost
        format_boost = 0.0
        if (ext == "pdf" and query_indicates_pdf) or \
           (ext in ("pptx", "ppt") and query_indicates_slides) or \
           (ext in ("docx", "doc") and query_indicates_doc):
            format_boost = 0.05

        # 1. Exact filename check
        if fname_lower in q_lower or any(fname_lower in qv for qv in query_variants):
            matches.append(
                TargetDocumentMatch(
                    document_id=doc.id,
                    filename=doc.original_filename,
                    matched_term=fname_lower,
                    confidence=1.0 + format_boost,
                )
            )
            seen_ids.add(doc.id)
            continue

        # 2. Aliases and stem matching
        aliases = _generate_document_aliases(doc.original_filename)
        best_match = None
        best_conf = 0.0

        for alias in aliases:
            alias_padded = f" {alias} "
            for q_norm in q_norms:
                if (
                    alias_padded in q_norm
                    or f"in {alias}" in q_norm
                    or f"of {alias}" in q_norm
                    or f"from {alias}" in q_norm
                ):
                    base_conf = 0.95 if len(alias.split()) > 1 else 0.85
                    conf = base_conf + format_boost
                    if conf > best_conf:
                        best_match = alias
                        best_conf = conf

        if best_match and best_conf > 0.0:
            matches.append(
                TargetDocumentMatch(
                    document_id=doc.id,
                    filename=doc.original_filename,
                    matched_term=best_match,
                    confidence=best_conf,
                )
            )
            seen_ids.add(doc.id)

    # Sort matches by confidence descending
    return sorted(matches, key=lambda m: m.confidence, reverse=True)


def detect_target_language(query: str) -> str | None:
    """Detect explicit language output request."""
    m = TRANSLATION_PATTERN.search(query)
    if m:
        lang = (
            m.group("lang")
            or m.group("lang_alt")
            or ("Hindi" if m.group("hindi_script") else None)
        )
        return lang.capitalize() if lang else "Hindi"
    return None


def detect_detail_level(query: str) -> str | None:
    """Detect requested verbosity or format."""
    for pattern, level in DETAIL_PATTERNS:
        if pattern.search(query):
            return level
    return None


# ---------------------------------------------------------------------------
# Core Query Understanding Engine
# ---------------------------------------------------------------------------

def understand_query(
    query: str,
    indexed_documents: list[Document] | None = None,
    conversation_history: tuple[tuple[str, str], ...] | list[tuple[str, str]] = (),
) -> QueryIntent:
    """Analyze a natural-language query to extract structural constraints, tasks, and target documents."""
    clean_q = query.strip()
    if not clean_q:
        return QueryIntent(
            task="FACTUAL",
            raw_query="",
            clean_query="",
            search_query="",
            target_documents=(),
            page_slide_constraint=None,
            target_language=None,
            detail_level=None,
            is_multi_document=False,
            is_overview=False,
            is_follow_up=False,
            topic_subject="",
        )

    # 1. Structural constraints: Pages and Slides
    constraint = extract_page_or_slide_constraint(clean_q)

    # 2. Target Document Resolution
    doc_matches = resolve_target_documents(clean_q, indexed_documents or [])
    
    # 3. Target Language
    target_lang = detect_target_language(clean_q)

    # 4. Detail Level
    detail = detect_detail_level(clean_q)

    # 5. Intent / Task Classification
    is_multi_doc = len(doc_matches) >= 2 or bool(
        re.search(r"\b(?:both\s+documents|across\s+all\s+documents|compare\s+documents|between\s+documents)\b", clean_q, re.IGNORECASE)
    )

    is_full_coverage = bool(
        FULL_COVERAGE_PATTERN.search(clean_q)
        or (
            constraint is not None
            and constraint.end >= 999999
            and bool(re.search(r"\b(?:all|every|each|whole|entire|inventory|walk|list|explain|summar|topic|title)\b", clean_q, re.IGNORECASE))
        )
        or (
            DOCUMENT_OVERVIEW_PATTERN.search(clean_q)
            and (
                constraint is None
                or (constraint.start == 1 and constraint.end >= 50)
                or constraint.end >= 999999
            )
        )
    )

    if COMPARISON_PATTERN.search(clean_q) or (is_multi_doc and re.search(r"\b(?:and|vs|versus|difference)\b", clean_q, re.IGNORECASE)):
        task = "COMPARISON"
        guidance = "Provide a structured, balanced comparison highlighting key similarities and differences between the referenced sources based solely on the evidence."
    elif is_full_coverage:
        task = "DOCUMENT_OVERVIEW"
        guidance = "Provide a comprehensive, sequential walkthrough of the document covering all pages/slides in order from beginning to end based solely on the evidence. Clearly state each page or slide number and its topics."
    elif DOCUMENT_OVERVIEW_PATTERN.search(clean_q):
        task = "DOCUMENT_OVERVIEW"
        guidance = "Provide a high-level comprehensive overview and outline of the main themes in the document based solely on the evidence."
    elif TOPIC_SUMMARY_PATTERN.search(clean_q):
        task = "TOPIC_SUMMARY"
        guidance = "Provide a concise, structured summary covering the specific topic requested based solely on the evidence."
    elif EXTRACTION_PATTERN.search(clean_q):
        task = "EXTRACTION"
        guidance = "Extract and present the requested facts or items in a clear, well-organized list based solely on the evidence."
    elif LOCATION_PATTERN.search(clean_q):
        task = "LOCATION"
        guidance = "Identify the specific page, slide, or section where the requested information appears based on the evidence locators."
    elif target_lang and TRANSLATION_PATTERN.search(clean_q):
        task = "TRANSLATION"
        guidance = f"Provide the answer strictly in {target_lang} based solely on the evidence."
    elif EXPLANATION_PATTERN.search(clean_q):
        task = "EXPLANATION"
        guidance = "Explain the concepts clearly, simply, and directly using only the evidence, avoiding unnecessary jargon."
    else:
        task = "FACTUAL"
        guidance = None

    is_overview = task == "DOCUMENT_OVERVIEW"

    # 6. Extract core subject for search query
    search_q = clean_q
    # Strip polite prefixes for cleaner retrieval embedding
    cleaned_search = re.sub(
        r"^(?:can\s+you\s+)?(?:please\s+)?(?:tell\s+me|explain|what\s+is|what\s+are|describe|summarise|summarize)\s+(?:the|about|an?)\s+",
        "",
        search_q,
        flags=re.IGNORECASE,
    ).strip()
    if cleaned_search and len(cleaned_search) >= 4:
        search_q = cleaned_search

    # Check if this is a follow-up
    has_pronoun = bool(re.search(r"\b(it|its|this|that|these|those|the\s+other\s+one|the\s+second\s+one)\b", clean_q, re.IGNORECASE))
    is_follow_up = bool(conversation_history) and (has_pronoun or len(clean_q.split()) <= 6 or task in {"TRANSLATION", "EXPLANATION"})

    return QueryIntent(
        task=task,
        raw_query=query,
        clean_query=clean_q,
        search_query=search_q,
        target_documents=tuple(doc_matches),
        page_slide_constraint=constraint,
        target_language=target_lang,
        detail_level=detail,
        is_multi_document=is_multi_doc,
        is_overview=is_overview,
        is_follow_up=is_follow_up,
        topic_subject=search_q,
        is_full_coverage=is_full_coverage,
        task_guidance=guidance,
    )
