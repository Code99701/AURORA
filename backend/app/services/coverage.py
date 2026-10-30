from dataclasses import dataclass
from html import escape
import json
import logging
import re
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm import LLMProvider, LLMProviderError
from app.models.content_unit import ContentUnit
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.workspace import Workspace
from app.rag.prompt import GroundedPrompt
from app.services.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_BATCH_MAX_CHARACTERS = 8000
DEFAULT_SINGLE_PASS_MAX_CHARACTERS = 12000


@dataclass(frozen=True)
class CoverageBatch:
    batch_index: int
    start_page: int
    end_page: int
    unit_label: str  # "Page" or "Slide"
    chunks: tuple[RetrievedChunk, ...]
    character_count: int


@dataclass(frozen=True)
class DocumentCoveragePlan:
    document_id: UUID
    filename: str
    total_units: int
    total_chunks: int
    start_page: int
    end_page: int
    unit_label: str  # "Page" or "Slide"
    batches: tuple[CoverageBatch, ...]
    all_chunks: tuple[RetrievedChunk, ...]
    empty_pages: tuple[int, ...]
    is_multi_batch: bool


def _format_evidence_block(item: RetrievedChunk, number: int) -> str:
    locator = (
        json.dumps(item.locator, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if item.locator is not None
        else "null"
    )
    return (
        f'<EVIDENCE number="{number}">\n'
        f"chunk_id: {item.chunk_id}\n"
        f"document_id: {item.document_id}\n"
        f"filename: {escape(item.filename)}\n"
        f"page_number: {item.page_number}\n"
        f"locator: {escape(locator)}\n"
        f"extraction_method: {escape(item.extraction_method or 'unknown')}\n"
        f"similarity: {item.similarity:.6f}\n"
        "<UNTRUSTED_DOCUMENT_TEXT>\n"
        f"{escape(item.text)}\n"
        "</UNTRUSTED_DOCUMENT_TEXT>\n"
        "</EVIDENCE>"
    )


def plan_document_coverage(
    db: Session,
    workspace: Workspace,
    document: Document,
    start_page: int | None = 1,
    end_page: int | None = None,
    max_batch_characters: int = DEFAULT_BATCH_MAX_CHARACTERS,
    max_single_pass_characters: int = DEFAULT_SINGLE_PASS_MAX_CHARACTERS,
) -> DocumentCoveragePlan:
    """Analyze a targeted document and partition all its content units/chunks into an ordered coverage plan."""
    if document.workspace_id != workspace.id:
        raise ValueError("Document does not belong to the authorized workspace")

    # 1. Inspect all content units in ordinal order to determine structure and empty units
    units = list(
        db.scalars(
            select(ContentUnit)
            .where(ContentUnit.document_id == document.id)
            .order_by(ContentUnit.ordinal.asc())
        ).all()
    )

    unit_label = "Slide" if any(u.kind == "SLIDE" for u in units) or document.original_filename.lower().endswith((".pptx", ".ppt")) else "Page"

    empty_pages = []
    for u in units:
        text = (u.text or "").strip()
        if not text or u.status == "SKIPPED":
            loc = u.locator or {}
            num = loc.get("slide") or loc.get("page") or (u.ordinal + 1)
            empty_pages.append(int(num))

    # 2. Query all chunks in chunk_index order with ContentUnit metadata
    chunk_stmt = (
        select(
            DocumentChunk,
            Document.original_filename,
            ContentUnit.locator,
            ContentUnit.extraction_method,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .outerjoin(ContentUnit, ContentUnit.id == DocumentChunk.content_unit_id)
        .where(
            DocumentChunk.document_id == document.id,
            Document.workspace_id == workspace.id,
            Document.indexing_status == "INDEXED",
        )
        .order_by(DocumentChunk.chunk_index.asc())
    )

    s_page = start_page or 1
    e_page = end_page if (end_page is not None and end_page < 999999) else 999999

    chunk_rows = db.execute(chunk_stmt).all()
    
    # Filter chunks matching the requested page span
    filtered_chunks: list[RetrievedChunk] = []
    for chunk, fname, locator, extraction_method in chunk_rows:
        chunk_start = chunk.page_start or chunk.page_number or 1
        chunk_end = chunk.page_end or chunk.page_number or chunk_start
        if chunk_end >= s_page and chunk_start <= e_page:
            sim = max(0.70, min(1.0, 0.99 - (0.001 * chunk.chunk_index)))
            filtered_chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    filename=fname,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    similarity=sim,
                    locator=locator,
                    extraction_method=extraction_method,
                )
            )

    if not filtered_chunks:
        return DocumentCoveragePlan(
            document_id=document.id,
            filename=document.original_filename,
            total_units=len(units),
            total_chunks=0,
            start_page=s_page,
            end_page=s_page,
            unit_label=unit_label,
            batches=(),
            all_chunks=(),
            empty_pages=tuple(empty_pages),
            is_multi_batch=False,
        )

    doc_min_page = min(
        (c.page_number for c in filtered_chunks if c.page_number is not None),
        default=s_page,
    )
    doc_max_page = max(
        (c.page_number for c in filtered_chunks if c.page_number is not None),
        default=s_page,
    )

    total_characters = sum(len(c.text) for c in filtered_chunks)

    # 3. Partition into batches
    batches: list[CoverageBatch] = []
    if total_characters <= max_single_pass_characters:
        # Fits comfortably in a single pass
        batches.append(
            CoverageBatch(
                batch_index=1,
                start_page=doc_min_page,
                end_page=doc_max_page,
                unit_label=unit_label,
                chunks=tuple(filtered_chunks),
                character_count=total_characters,
            )
        )
        is_multi_batch = False
    else:
        # Partition into contiguous bounded batches
        current_batch_chunks: list[RetrievedChunk] = []
        current_batch_chars = 0
        batch_idx = 1
        for c in filtered_chunks:
            c_len = len(c.text)
            if current_batch_chunks and (current_batch_chars + c_len > max_batch_characters):
                b_start = min((ch.page_number for ch in current_batch_chunks if ch.page_number is not None), default=1)
                b_end = max((ch.page_number for ch in current_batch_chunks if ch.page_number is not None), default=b_start)
                batches.append(
                    CoverageBatch(
                        batch_index=batch_idx,
                        start_page=b_start,
                        end_page=b_end,
                        unit_label=unit_label,
                        chunks=tuple(current_batch_chunks),
                        character_count=current_batch_chars,
                    )
                )
                batch_idx += 1
                current_batch_chunks = [c]
                current_batch_chars = c_len
            else:
                current_batch_chunks.append(c)
                current_batch_chars += c_len
        if current_batch_chunks:
            b_start = min((ch.page_number for ch in current_batch_chunks if ch.page_number is not None), default=1)
            b_end = max((ch.page_number for ch in current_batch_chunks if ch.page_number is not None), default=b_start)
            batches.append(
                CoverageBatch(
                    batch_index=batch_idx,
                    start_page=b_start,
                    end_page=b_end,
                    unit_label=unit_label,
                    chunks=tuple(current_batch_chunks),
                    character_count=current_batch_chars,
                )
            )
        is_multi_batch = len(batches) > 1

    return DocumentCoveragePlan(
        document_id=document.id,
        filename=document.original_filename,
        total_units=len(units),
        total_chunks=len(filtered_chunks),
        start_page=doc_min_page,
        end_page=doc_max_page,
        unit_label=unit_label,
        batches=tuple(batches),
        all_chunks=tuple(filtered_chunks),
        empty_pages=tuple(empty_pages),
        is_multi_batch=is_multi_batch,
    )


def build_coverage_prompt(
    plan: DocumentCoveragePlan,
    query: str,
    chunks: tuple[RetrievedChunk, ...] | None = None,
    answer_language: str | None = None,
    range_override: tuple[int, int] | None = None,
) -> GroundedPrompt:
    """Construct a grounded prompt enforcing sequential, section-by-section walkthrough without omissions."""
    use_chunks = chunks if chunks is not None else plan.all_chunks
    evidence_blocks = "\n\n".join(
        _format_evidence_block(item, idx + 1) for idx, item in enumerate(use_chunks)
    )

    r_start = range_override[0] if range_override else plan.start_page
    r_end = range_override[1] if range_override else plan.end_page

    empty_note = ""
    if plan.empty_pages:
        empty_str = ", ".join(str(p) for p in sorted(plan.empty_pages))
        empty_note = f"\nTransparency notice: Note that the following {plan.unit_label.lower()}s contained figures/media without extractable text: {empty_str}."

    guidance = (
        f"You are providing an exhaustive, sequential document walkthrough of '{plan.filename}' "
        f"covering {plan.unit_label.lower()}s {r_start} to {r_end} from beginning to end.\n\n"
        f"STRICT RULES:\n"
        f"1. Walk through all available {plan.unit_label.lower()}s in sequential order without skipping sections.\n"
        f"2. For each {plan.unit_label.lower()}, clearly state the {plan.unit_label} number and summarize its main topics, definitions, and concepts.\n"
        f"3. Base every statement strictly and solely on the provided evidence.\n"
        f"4. Do not invent facts or cite pages not present in the evidence.{empty_note}"
    )

    system_instruction = (
        "You are AURORA, a document-grounded research assistant providing comprehensive document coverage.\n\n"
        "Answer only from the retrieved evidence supplied by the application. Do not use general knowledge "
        "to fill gaps and do not invent facts. Provide a complete, structured, sequential overview covering all "
        f"relevant {plan.unit_label.lower()}s present in the evidence."
    )

    lang_pref = (
        f"Answer language preference: {escape(answer_language)}."
        if answer_language
        else "Answer in the language of the user's question."
    )

    user_prompt = (
        "USER QUESTION\n"
        "<QUESTION>\n"
        f"{escape(query)}\n"
        "</QUESTION>\n\n"
        f"{lang_pref}\n\n"
        "TASK GUIDANCE\n"
        f"{guidance}\n\n"
        "RETRIEVED EVIDENCE\n"
        "<AUTHORIZED_EVIDENCE>\n"
        f"{evidence_blocks}\n"
        "</AUTHORIZED_EVIDENCE>\n\n"
        f"Produce a structured sequential walkthrough covering all {plan.unit_label.lower()}s."
    )

    return GroundedPrompt(system_instruction, user_prompt)


def execute_multi_batch_coverage(
    plan: DocumentCoveragePlan,
    llm_provider: LLMProvider,
    query: str,
    answer_language: str | None = None,
) -> str:
    """Execute sequential batch summarization and synthesis for documents exceeding single-context budgets."""
    if not plan.all_chunks:
        return f"No readable text content was found in {plan.filename}."

    if not plan.is_multi_batch:
        prompt = build_coverage_prompt(plan, query, answer_language=answer_language)
        result = llm_provider.generate(prompt.system_instruction, prompt.user_prompt)
        return result.text

    # Multi-batch execution: summarize each batch in order
    batch_summaries: list[str] = []
    for batch in plan.batches:
        logger.info(
            "Summarizing coverage batch %d/%d (%ss %d-%d) for %s",
            batch.batch_index,
            len(plan.batches),
            batch.unit_label,
            batch.start_page,
            batch.end_page,
            plan.filename,
        )
        batch_prompt = build_coverage_prompt(
            plan,
            query=f"Summarize {batch.unit_label}s {batch.start_page} to {batch.end_page} of {plan.filename} in sequential order.",
            chunks=batch.chunks,
            answer_language=answer_language,
            range_override=(batch.start_page, batch.end_page),
        )
        batch_result = llm_provider.generate(
            batch_prompt.system_instruction, batch_prompt.user_prompt
        )
        batch_summaries.append(
            f"### {batch.unit_label}s {batch.start_page} – {batch.end_page}\n\n{batch_result.text.strip()}"
        )

    # Synthesize complete document walkthrough
    combined_body = "\n\n".join(batch_summaries)
    
    empty_notice = ""
    if plan.empty_pages:
        empty_str = ", ".join(str(p) for p in sorted(plan.empty_pages))
        empty_notice = f"\n\n> **Note:** The following {plan.unit_label.lower()}s contain figures, diagrams, or media without extractable text: {empty_str}."

    final_overview = (
        f"## Document Overview: {plan.filename}\n\n"
        f"Comprehensive sequential walkthrough covering {plan.unit_label.lower()}s {plan.start_page} to {plan.end_page}:\n\n"
        f"{combined_body}"
        f"{empty_notice}"
    )
    return final_overview
