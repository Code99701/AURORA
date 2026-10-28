"""Context-aware query rewriter for multi-turn RAG in AURORA.

Resolves follow-up queries (pronouns, ellipses, translations, numbered references)
into standalone search queries before evidence retrieval.

Design Principles:
1. Fast-path deterministic resolution for predictable patterns (zero API calls, 0ms latency).
2. Page range and document constraint preservation.
3. Safe fallback to original query if ambiguous or unresolvable.
4. Bounded LLM rewrite fallback without retry storms on rate-limit/quota errors.
5. Strict separation between retrieval search query and response evidence prompt.
"""

from dataclasses import dataclass
import logging
import re
from typing import Any

from app.llm.base import (
    LLMProvider,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RewriteResult:
    rewritten_query: str
    detected_language: str | None = None
    is_follow_up: bool = False
    resolution_method: str = "original"


# ---------------------------------------------------------------------------
# Regex Patterns for Deterministic Fast-Path
# ---------------------------------------------------------------------------

TRANSLATION_PATTERN = re.compile(
    r"\b(?:translate|translation)\b.*?\b(?:(?:in|into|to)\s+(?P<lang>[A-Za-z]+))|"
    r"\b(?P<lang_alt>hindi|english)\s+(?:me|mein)\s+(?:translate|samjhao|batao)\b|"
    r"(?P<hindi_script>हिंदी\s*में\s*(?:अनुवाद|समझाइए)|अनुवाद\s*करें)",
    re.IGNORECASE,
)

SIMPLIFY_PATTERN = re.compile(
    r"\b(?:explain\s+(?:it|this|that|more|again)|simpler|more\s+simply|simple\s+terms|in\s+simple\s+words|"
    r"in\s+3\s+lines|summarise\s+(?:this|that|it)|summarize\s+(?:this|that|it)|"
    r"give\s+me\s+more\s+details|tell\s+me\s+more|give\s+me\s+a\s+shorter\s+version|shorter\s+version|more\s+details|in\s+detail)\b",
    re.IGNORECASE,
)

COMPARISON_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:(?:now\s+)?compare\s+(?:it|this|that)\s+(?:with|to)|how\s+does\s+(?:it|this|that)\s+compare\s+(?:with|to))\s+(?P<target>.+)\b",
    re.IGNORECASE,
)

LOCATION_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:where\s+is\s+(?:this|that|it)\s+(?:mentioned|found|written|stated)|which\s+page\s+is\s+(?:this|that|it)\s+on|which\s+slide\s+is\s+(?:this|that|it)\s+on)\b",
    re.IGNORECASE,
)

ORDINAL_MAP = {
    "first": 1, "1st": 1, "#1": 1, "1": 1,
    "second": 2, "2nd": 2, "#2": 2, "2": 2,
    "third": 3, "3rd": 3, "#3": 3, "3": 3,
    "fourth": 4, "4th": 4, "#4": 4, "4": 4,
    "fifth": 5, "5th": 5, "#5": 5, "5": 5,
}

NUMBERED_REF_PATTERN = re.compile(
    r"\b(?:the\s+)?(?P<ordinal>first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|#?[1-5])\s+(?:one|item|option|point|topic|section|document|pdf|slide)\b|"
    r"\b(?:option|item|point|topic|document|slide)\s+(?P<num>[1-5])\b",
    re.IGNORECASE,
)

PRONOUN_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:what\s+are\s+(?:its|the)\s+(?P<attr_pl>[a-zA-Z\s]+?)(?:\s+of\s+(?:it|this|that))?\??$)|"
    r"\b(?:what\s+is\s+(?:its|the)\s+(?P<attr_sg>[a-zA-Z\s]+?)(?:\s+of\s+(?:it|this|that))?\??$)|"
    r"\b(?:how\s+does\s+(?:it|this|that)\s+(?P<verb>work|function|operate)\??$)",
    re.IGNORECASE,
)

PAGE_CONSTRAINT_PATTERN = re.compile(
    r"\b(?:(?:pages?|slides?)\s+\d+(?:\s*(?:to|-|through)\s*\d+)?|first\s+\d+\s+(?:pages?|slides?)|slide\s+#?\d+)\b",
    re.IGNORECASE,
)

QUESTION_PREFIX_PATTERNS = [
    re.compile(r"^(?:can\s+you\s+)?(?:please\s+)?(?:explain|tell\s+me\s+about|describe|summarise|summarize|give\s+(?:an?\s+)?overview\s+of)\s+(?:the\s+|an?\s+)?", re.IGNORECASE),
    re.compile(r"^what\s+(?:is|are|was|were)\s+(?:the\s+|an?\s+)?", re.IGNORECASE),
    re.compile(r"^(?:explain|describe|tell\s+me\s+about|give\s+details\s+on|discuss)\s+(?:the\s+|an?\s+)?", re.IGNORECASE),
    re.compile(r"^how\s+does\s+(?:the\s+|an?\s+)?", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helper Extraction Functions
# ---------------------------------------------------------------------------

def extract_core_subject(query: str) -> str:
    """Extract clean subject phrase from a user query by removing question boilerplate."""
    cleaned = query.strip().rstrip("?.!")
    for pattern in QUESTION_PREFIX_PATTERNS:
        m = pattern.match(cleaned)
        if m:
            cleaned = cleaned[m.end():].strip()
            break
    # Strip polite suffixes
    cleaned = re.sub(r"\b(?:please|in\s+detail|briefly|in\s+simple\s+words)\b", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else query.strip()


def get_last_turns(
    history: tuple[tuple[str, str], ...] | list[tuple[str, str]]
) -> tuple[str | None, str | None]:
    """Extract (last_user_query, last_assistant_response) from history tuples."""
    last_user = None
    last_assistant = None
    for role, text in reversed(history):
        if role.lower() == "assistant" and last_assistant is None:
            last_assistant = text
        elif role.lower() == "user" and last_user is None:
            last_user = text
        if last_user is not None and last_assistant is not None:
            break
    return last_user, last_assistant


def extract_numbered_items(text: str) -> dict[int, str]:
    """Parse numbered or bulleted items from assistant text."""
    items: dict[int, str] = {}
    lines = text.splitlines()
    for line in lines:
        m = re.match(r"^\s*(?:[-*]\s+)?(?P<num>\d+)[\.\)]\s+(?P<content>.+)$", line)
        if m:
            n = int(m.group("num"))
            item_text = m.group("content").strip()
            # Clean formatting like bold **Item**
            item_text = re.sub(r"^\*\*([^*]+)\*\*:?.*", r"\1", item_text)
            items[n] = item_text[:120].strip()
    if not items:
        bullet_idx = 1
        for line in lines:
            m = re.match(r"^\s*[-*•]\s+(?P<content>.+)$", line)
            if m:
                item_text = m.group("content").strip()
                item_text = re.sub(r"^\*\*([^*]+)\*\*:?.*", r"\1", item_text)
                items[bullet_idx] = item_text[:120].strip()
                bullet_idx += 1
    return items


# ---------------------------------------------------------------------------
# Core Query Rewriter Function
# ---------------------------------------------------------------------------

def rewrite_query_for_retrieval(
    query: str,
    conversation_history: tuple[tuple[str, str], ...] | list[tuple[str, str]] = (),
    llm_provider: LLMProvider | None = None,
) -> RewriteResult:
    """Rewrite a user message into a standalone search query using recent conversation turns.

    Uses deterministic heuristics for common follow-up templates (translations,
    pronoun lookups, list ordinal references, simple simplifications).
    Falls back gracefully without breaking retrieval if references are ambiguous.
    """
    clean_query = query.strip()
    if not clean_query:
        return RewriteResult(rewritten_query="", is_follow_up=False, resolution_method="empty")

    if not conversation_history:
        return RewriteResult(rewritten_query=clean_query, is_follow_up=False, resolution_method="no_history")

    last_user, last_assistant = get_last_turns(conversation_history)
    if not last_user:
        return RewriteResult(rewritten_query=clean_query, is_follow_up=False, resolution_method="no_user_turn")

    last_subject = extract_core_subject(last_user)

    # 0. Context boundary protection:
    # If the user's message is an explicit, self-contained question without backward pronouns,
    # prevent past conversation topics or documents from overriding the new query.
    has_pronoun = bool(
        re.search(
            r"\b(it|its|this|that|these|those|them|their|the\s+other\s+one|the\s+second\s+one|the\s+first\s+one)\b",
            clean_query,
            re.IGNORECASE,
        )
    )
    is_explicit_independent = (
        not has_pronoun
        and not TRANSLATION_PATTERN.search(clean_query)
        and not NUMBERED_REF_PATTERN.search(clean_query)
        and not SIMPLIFY_PATTERN.search(clean_query)
        and not COMPARISON_FOLLOWUP_PATTERN.search(clean_query)
        and not LOCATION_FOLLOWUP_PATTERN.search(clean_query)
        and not PAGE_CONSTRAINT_PATTERN.search(clean_query)
        and len(clean_query.split()) >= 4
    )
    if is_explicit_independent:
        return RewriteResult(
            rewritten_query=clean_query,
            is_follow_up=False,
            resolution_method="independent_context_boundary",
        )

    # 1. Deterministic translation follow-ups
    # e.g. "Translate that into Hindi", "Translate to Hindi", "Hindi me samjhao"
    trans_m = TRANSLATION_PATTERN.search(clean_query)
    if trans_m:
        lang = (
            trans_m.group("lang")
            or trans_m.group("lang_alt")
            or ("Hindi" if trans_m.group("hindi_script") else None)
        )
        detected_lang = lang.capitalize() if lang else "Hindi"
        # Search query is the original subject/query to retrieve the grounding evidence
        return RewriteResult(
            rewritten_query=last_user,
            detected_language=detected_lang,
            is_follow_up=True,
            resolution_method="deterministic_translation",
        )

    # 1b. Deterministic comparison follow-ups
    # e.g. "Now compare it with the other document", "How does that compare with the ML book?"
    comp_m = COMPARISON_FOLLOWUP_PATTERN.search(clean_query)
    if comp_m and last_subject:
        target = comp_m.group("target").strip().rstrip("?.!")
        rewritten = f"Compare {last_subject} with {target}"
        return RewriteResult(
            rewritten_query=rewritten,
            is_follow_up=True,
            resolution_method="deterministic_comparison_followup",
        )

    # 1c. Deterministic location follow-ups
    # e.g. "Where is this mentioned?", "Which page is that on?"
    loc_m = LOCATION_FOLLOWUP_PATTERN.search(clean_query)
    if loc_m and last_subject:
        rewritten = f"Where is {last_subject} mentioned?"
        return RewriteResult(
            rewritten_query=rewritten,
            is_follow_up=True,
            resolution_method="deterministic_location_followup",
        )

    # 2. Deterministic numbered item references
    # e.g. "Summarise the second one", "Explain option 2", "Tell me about the 1st one"
    num_m = NUMBERED_REF_PATTERN.search(clean_query)
    if num_m and last_assistant:
        ord_str = (num_m.group("ordinal") or num_m.group("num") or "").lower()
        idx = ORDINAL_MAP.get(ord_str)
        if idx:
            items = extract_numbered_items(last_assistant)
            if idx in items:
                referenced_item = items[idx]
                # Combine referenced item with query intent
                action = re.sub(NUMBERED_REF_PATTERN, "", clean_query).strip()
                rewritten = f"{referenced_item} {action}".strip() if action else referenced_item
                return RewriteResult(
                    rewritten_query=rewritten,
                    is_follow_up=True,
                    resolution_method="deterministic_numbered",
                )

    # 3. Deterministic pronoun / attribute follow-ups
    # e.g. "What are its advantages?", "How does it work?", "What are the limitations of this?"
    attr_m = PRONOUN_FOLLOWUP_PATTERN.search(clean_query)
    if attr_m and last_subject:
        if attr_m.group("attr_pl"):
            attr = attr_m.group("attr_pl").strip()
            rewritten = f"What are the {attr} of {last_subject}?"
        elif attr_m.group("attr_sg"):
            attr = attr_m.group("attr_sg").strip()
            rewritten = f"What is the {attr} of {last_subject}?"
        elif attr_m.group("verb"):
            verb = attr_m.group("verb").strip()
            rewritten = f"How does {last_subject} {verb}?"
        else:
            rewritten = f"{last_subject} {clean_query}"
        return RewriteResult(
            rewritten_query=rewritten,
            is_follow_up=True,
            resolution_method="deterministic_pronoun",
        )

    # 4. Simplification and clarification follow-ups
    # e.g. "Explain it more simply", "Can you explain that again in simple terms?"
    if SIMPLIFY_PATTERN.search(clean_query) and last_subject:
        # Check if query also contains an explicit page constraint
        page_constraint = PAGE_CONSTRAINT_PATTERN.search(clean_query)
        if page_constraint:
            rewritten = f"{last_subject} {page_constraint.group(0)}"
        else:
            rewritten = last_subject
        return RewriteResult(
            rewritten_query=rewritten,
            is_follow_up=True,
            resolution_method="deterministic_simplification",
        )

    # 5. Elliptical page-range follow-ups
    # e.g. "What about pages 2 to 5?", "What about page 3?", "On page 4"
    page_constraint = PAGE_CONSTRAINT_PATTERN.search(clean_query)
    if page_constraint and last_subject and len(clean_query.split()) <= 8:
        rewritten = f"{last_subject} {page_constraint.group(0)}"
        return RewriteResult(
            rewritten_query=rewritten,
            is_follow_up=True,
            resolution_method="deterministic_page_constraint",
        )

    # 5. Direct pronoun replacement in short elliptical queries
    # e.g. "What about its architecture?", "Tell me about this"
    has_pronoun = bool(re.search(r"\b(it|its|this|that|these|those)\b", clean_query, re.IGNORECASE))
    if has_pronoun and last_subject and len(clean_query.split()) <= 10:
        page_constraint = PAGE_CONSTRAINT_PATTERN.search(clean_query)
        substituted = re.sub(r"\b(?:its)\b", f"{last_subject}'s", clean_query, flags=re.IGNORECASE)
        substituted = re.sub(r"\b(?:it|this|that)\b", last_subject, substituted, flags=re.IGNORECASE)
        if page_constraint and page_constraint.group(0).casefold() not in substituted.casefold():
            substituted = f"{substituted} {page_constraint.group(0)}"
        return RewriteResult(
            rewritten_query=substituted,
            is_follow_up=True,
            resolution_method="deterministic_substitution",
        )

    # 6. Optional LLM rewrite fallback for complex multi-turn queries
    # Only invoked if llm_provider is passed, query has follow-up signals, and deterministic rules did not fire
    if llm_provider is not None and (has_pronoun or len(clean_query.split()) <= 6):
        try:
            recent_turns = list(conversation_history)[-4:]
            formatted_turns = "\n".join(f"{r.capitalize()}: {t[:250]}" for r, t in recent_turns)
            rewrite_system_instruction = (
                "You are an expert search query rewriter for a document retrieval engine.\n"
                "Rewrite the user's follow-up message into a standalone search query using recent turns.\n"
                "Rules:\n"
                "1. Output ONLY the rewritten search query. No markdown, no quotes, no explanations.\n"
                "2. Preserve all explicit page numbers (e.g. 'page 3') and document names.\n"
                "3. Do NOT invent new entities, facts, or document names not in the conversation.\n"
                "4. If already standalone or ambiguous, output the original query unchanged."
            )
            rewrite_prompt = (
                f"Recent Conversation:\n{formatted_turns}\n\n"
                f"Follow-up User Query: {clean_query}\n\n"
                "Standalone Search Query:"
            )
            gen = llm_provider.generate(rewrite_system_instruction, rewrite_prompt)
            candidate = gen.text.strip().strip('"').strip("'").splitlines()[0].strip()
            if candidate and len(candidate) <= 300 and candidate.casefold() != clean_query.casefold():
                return RewriteResult(
                    rewritten_query=candidate,
                    is_follow_up=True,
                    resolution_method="llm",
                )
        except (LLMQuotaExhaustedError, LLMRateLimitError, LLMProviderError, Exception) as exc:
            logger.info("LLM query rewrite skipped due to provider limit/error: %s", exc)

    # 7. Safe Fallback: Return original query unchanged
    return RewriteResult(
        rewritten_query=clean_query,
        is_follow_up=False,
        resolution_method="fallback_original",
    )
