from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.embeddings import EmbeddingProvider
from app.llm import (
    LLMProvider,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
)
from app.models.workspace import Workspace
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.rag_citation import RAGCitation
from app.models.rag_response import RAGResponseRecord
from app.rag.context import build_context
from app.rag.prompt import build_grounded_prompt
from app.rag.prompt import GroundedPrompt
from app.rag.rewriter import rewrite_query_for_retrieval
from app.rag.understanding import understand_query
from app.services.coverage import (
    DocumentCoveragePlan,
    build_coverage_prompt,
    execute_multi_batch_coverage,
    plan_document_coverage,
)
from app.services.retrieval import RetrievedChunk
from app.services import retrieval as retrieval_service


INSUFFICIENT_EVIDENCE_ANSWER = (
    "I couldn't find enough information in your authorized documents "
    "to answer this reliably."
)


class RAGError(Exception):
    def __init__(self, code: str, public_message: str, status_code: int):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


@dataclass(frozen=True)
class SourceReference:
    citation_id: UUID
    position: int
    document_id: UUID
    chunk_id: UUID
    filename: str
    page_number: int | None
    similarity: float
    locator: dict | None = None
    extraction_method: str | None = None


@dataclass(frozen=True)
class RAGResult:
    response_id: UUID
    answer: str
    sources: tuple[SourceReference, ...]
    insufficient_evidence: bool
    model: str | None


@dataclass(frozen=True)
class RAGPreparation:
    """Authorized retrieval output shared by synchronous and streaming generation."""

    query: str
    answer_language: str | None
    top_k: int
    evidence: tuple[RetrievedChunk, ...]
    prompt: GroundedPrompt | None
    search_query: str | None = None
    coverage_plan: DocumentCoveragePlan | None = None

    @property
    def insufficient_evidence(self) -> bool:
        return self.prompt is None


def _deduplicate_evidence(items):
    """Keep unique chunks and suppress duplicate text within the same document."""
    seen: set[UUID] = set()
    seen_text: set[tuple[object, str]] = set()
    unique = []
    for item in items:
        text_fingerprint = (item.document_id, " ".join(item.text.casefold().split()))
        if item.chunk_id in seen or text_fingerprint in seen_text:
            continue
        seen.add(item.chunk_id)
        seen_text.add(text_fingerprint)
        unique.append(item)
    return unique


def _persist_response(
    db: Session,
    workspace: Workspace,
    requested_by: int,
    query: str,
    answer: str,
    answer_language: str | None,
    top_k: int,
    insufficient_evidence: bool,
    model: str | None,
    evidence,
    commit: bool = True,
) -> RAGResult:
    chunk_ids = [item.chunk_id for item in evidence]
    authorized_rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.id.in_(chunk_ids),
            Document.workspace_id == workspace.id,
        )
    ).all() if chunk_ids else []
    authorized_chunks = {chunk.id: (chunk, document) for chunk, document in authorized_rows}
    if len(authorized_chunks) != len(chunk_ids):
        db.rollback()
        raise RAGError(
            "RAG_PERSISTENCE_ERROR",
            "Generated response evidence could not be validated",
            500,
        )

    record = RAGResponseRecord(
        workspace_id=workspace.id,
        requested_by=requested_by,
        query=query,
        answer=answer,
        answer_language=answer_language,
        top_k=top_k,
        citation_count=len(evidence),
        insufficient_evidence=insufficient_evidence,
        model=model,
    )
    try:
        db.add(record)
        db.flush()
        citations = [
            RAGCitation(
                response_id=record.id,
                chunk_id=item.chunk_id,
                position=position,
                similarity=item.similarity,
            )
            for position, item in enumerate(evidence, start=1)
        ]
        db.add_all(citations)
        db.flush()
        sources = tuple(
            SourceReference(
                citation_id=citation.id,
                position=citation.position,
                document_id=authorized_chunks[item.chunk_id][1].id,
                chunk_id=item.chunk_id,
                filename=authorized_chunks[item.chunk_id][1].original_filename,
                page_number=authorized_chunks[item.chunk_id][0].page_number,
                similarity=item.similarity,
                locator=(
                    authorized_chunks[item.chunk_id][0].content_unit.locator
                    if authorized_chunks[item.chunk_id][0].content_unit is not None
                    else None
                ),
                extraction_method=(
                    authorized_chunks[item.chunk_id][0].content_unit.extraction_method
                    if authorized_chunks[item.chunk_id][0].content_unit is not None
                    else None
                ),
            )
            for citation, item in zip(citations, evidence, strict=True)
        )
        if commit:
            db.commit()
        return RAGResult(
            response_id=record.id,
            answer=record.answer,
            sources=sources,
            insufficient_evidence=record.insufficient_evidence,
            model=record.model,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise RAGError(
            "RAG_PERSISTENCE_ERROR",
            "Generated response and citations could not be saved",
            500,
        ) from exc


def prepare_question(
    db: Session,
    workspace: Workspace,
    query: str,
    top_k: int,
    answer_language: str | None,
    embedding_provider: EmbeddingProvider,
    conversation_history: tuple[tuple[str, str], ...] = (),
    llm_provider: LLMProvider | None = None,
) -> RAGPreparation:
    """Retrieve and bound authorized evidence without invoking an LLM for generation."""
    search_query = query
    effective_language = answer_language
    if conversation_history:
        rewrite_result = rewrite_query_for_retrieval(
            query=query,
            conversation_history=conversation_history,
            llm_provider=llm_provider,
        )
        if rewrite_result.rewritten_query:
            search_query = rewrite_result.rewritten_query
        if rewrite_result.detected_language and not effective_language:
            effective_language = rewrite_result.detected_language

    indexed_docs = (
        list(
            db.scalars(
                select(Document).where(
                    Document.workspace_id == workspace.id,
                    Document.indexing_status == "INDEXED",
                )
            ).all()
        )
        if hasattr(db, "scalars")
        else []
    )
    intent = understand_query(query, indexed_docs, conversation_history)
    if intent.target_language and not effective_language:
        effective_language = intent.target_language

    # Check for targeted document coverage request
    target_docs = [
        d for d in indexed_docs
        if any(m.document_id == d.id for m in intent.target_documents)
    ]
    target_doc = target_docs[0] if target_docs else (indexed_docs[0] if len(indexed_docs) == 1 and getattr(intent, "is_full_coverage", False) else None)

    if (getattr(intent, "is_full_coverage", False) or intent.task == "DOCUMENT_OVERVIEW") and target_doc is not None:
        s_page = intent.page_slide_constraint.start if intent.page_slide_constraint else 1
        e_page = intent.page_slide_constraint.end if intent.page_slide_constraint else None
        coverage_plan = plan_document_coverage(
            db=db,
            workspace=workspace,
            document=target_doc,
            start_page=s_page,
            end_page=e_page,
        )
        if coverage_plan.all_chunks:
            prompt = build_coverage_prompt(
                coverage_plan,
                query=query,
                answer_language=effective_language,
            )
            return RAGPreparation(
                query=query,
                answer_language=effective_language,
                top_k=len(coverage_plan.all_chunks),
                evidence=coverage_plan.all_chunks,
                prompt=prompt,
                search_query=search_query,
                coverage_plan=coverage_plan,
            )

    try:
        import inspect
        sig = inspect.signature(retrieval_service.search_workspace)
        if "intent" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            retrieved = retrieval_service.search_workspace(
                db, workspace, search_query, top_k, embedding_provider, intent=intent
            )
        else:
            retrieved = retrieval_service.search_workspace(
                db, workspace, search_query, top_k, embedding_provider
            )
    except TypeError:
        retrieved = retrieval_service.search_workspace(
            db, workspace, search_query, top_k, embedding_provider
        )
    except retrieval_service.RetrievalError as exc:
        if exc.code in {"NO_RESEARCH_READY_SOURCES", "INDEX_MODEL_MISMATCH"}:
            raise RAGError(exc.code, exc.public_message, 409) from exc
        raise RAGError(
            "RAG_RETRIEVAL_ERROR", "Authorized evidence retrieval failed", exc.status_code
        ) from exc

    relevant = _deduplicate_evidence(
        [item for item in retrieved if item.similarity >= settings.RAG_MIN_SIMILARITY]
    )
    context = build_context(relevant, settings.RAG_CONTEXT_MAX_CHARACTERS)
    prompt = (
        build_grounded_prompt(
            query,
            context.text,
            effective_language,
            conversation_history,
            task_guidance=intent.task_guidance,
        )
        if context.evidence
        else None
    )
    return RAGPreparation(
        query=query,
        answer_language=effective_language,
        top_k=top_k,
        evidence=context.evidence,
        prompt=prompt,
        search_query=search_query,
    )


def require_research_ready(db: Session, workspace: Workspace) -> None:
    """Reject before provider use when the workspace has no indexed evidence."""
    if not retrieval_service.has_research_ready_sources(db, workspace):
        raise RAGError(
            "NO_RESEARCH_READY_SOURCES",
            "Process and index a workspace document before asking a grounded question",
            409,
        )


def is_model_refusal(text: str) -> bool:
    """Detect if the generated answer is an explicit refusal due to lack of evidence."""
    lowered = text.casefold()
    refusal_phrases = (
        "couldn't find enough information",
        "could not find enough information",
        "does not contain enough information",
        "do not contain enough information",
        "provided context does not contain",
        "provided documents do not contain",
        "provided text does not contain",
        "provided evidence does not contain",
        "provided sources do not contain",
        "retrieved evidence does not contain",
        "retrieved documents do not contain",
        "no information is provided in the",
        "no information is available in the",
        "not mentioned in the provided",
        "not found in the provided",
        "not mentioned in the authorized",
        "not found in the authorized",
        "do not mention",
        "does not mention",
        "authorized documents do not contain",
        "authorized documents to answer this",
        "cannot find any mention of",
        "can't find any mention of",
        "there is no mention of",
        "पर्याप्त जानकारी नहीं",
        "उल्लेख नहीं है",
    )
    return any(p in lowered for p in refusal_phrases)


def persist_prepared_answer(
    db: Session,
    workspace: Workspace,
    requested_by: int,
    preparation: RAGPreparation,
    answer: str,
    model: str | None,
    commit: bool = True,
) -> RAGResult:
    """Persist one completed answer and its server-authorized evidence graph."""
    refusal = preparation.insufficient_evidence or is_model_refusal(answer)
    evidence_to_persist = [] if refusal else list(preparation.evidence)
    return _persist_response(
        db=db,
        workspace=workspace,
        requested_by=requested_by,
        query=preparation.query,
        answer=answer,
        answer_language=preparation.answer_language,
        top_k=preparation.top_k,
        insufficient_evidence=refusal,
        model=model,
        evidence=evidence_to_persist,
        commit=commit,
    )


def answer_question(
    db: Session,
    workspace: Workspace,
    requested_by: int,
    query: str,
    top_k: int,
    answer_language: str | None,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    conversation_history: tuple[tuple[str, str], ...] = (),
    persist_commit: bool = True,
) -> RAGResult:
    """Coordinate one-shot RAG over evidence authorized by the retriever."""
    preparation = prepare_question(
        db=db,
        workspace=workspace,
        query=query,
        top_k=top_k,
        answer_language=answer_language,
        embedding_provider=embedding_provider,
        conversation_history=conversation_history,
        llm_provider=llm_provider,
    )
    if preparation.insufficient_evidence:
        return persist_prepared_answer(
            db,
            workspace,
            requested_by,
            preparation,
            INSUFFICIENT_EVIDENCE_ANSWER,
            None,
            persist_commit,
        )
    if preparation.coverage_plan and getattr(preparation.coverage_plan, "is_multi_batch", False):
        try:
            answer_text = execute_multi_batch_coverage(
                plan=preparation.coverage_plan,
                llm_provider=llm_provider,
                query=query,
                answer_language=answer_language,
            )
        except LLMQuotaExhaustedError as exc:
            raise RAGError("LLM_QUOTA_EXHAUSTED", str(exc), 429) from exc
        except LLMRateLimitError as exc:
            raise RAGError("LLM_RATE_LIMIT_ERROR", "Generation service is temporarily rate limited", 503) from exc
        except LLMProviderError as exc:
            raise RAGError("LLM_PROVIDER_ERROR", "Grounded answer generation failed", 503) from exc
        return persist_prepared_answer(
            db,
            workspace,
            requested_by,
            preparation,
            answer_text,
            llm_provider.model_name,
            persist_commit,
        )
    assert preparation.prompt is not None
    try:
        generation = llm_provider.generate(
            preparation.prompt.system_instruction, preparation.prompt.user_prompt
        )
    except LLMQuotaExhaustedError as exc:
        raise RAGError(
            "LLM_QUOTA_EXHAUSTED",
            str(exc),
            429,
        ) from exc
    except LLMRateLimitError as exc:
        raise RAGError(
            "LLM_RATE_LIMIT_ERROR",
            "Generation service is temporarily rate limited",
            503,
        ) from exc
    except LLMProviderError as exc:
        raise RAGError(
            "LLM_PROVIDER_ERROR", "Grounded answer generation failed", 503
        ) from exc

    return persist_prepared_answer(
        db,
        workspace,
        requested_by,
        preparation,
        generation.text,
        generation.model_name,
        persist_commit,
    )


def get_response(
    db: Session, workspace: Workspace, response_id: UUID
) -> RAGResult | None:
    """Resolve one response and its live citations inside the workspace boundary."""
    return get_responses(db, workspace, [response_id]).get(response_id)


def get_citation_source(
    db: Session, workspace: Workspace, citation_id: UUID
) -> SourceReference | None:
    """Resolve client-visible citation identity to authoritative live provenance."""
    row = db.execute(
        select(RAGCitation, RAGResponseRecord, DocumentChunk, Document)
        .join(RAGResponseRecord, RAGResponseRecord.id == RAGCitation.response_id)
        .join(DocumentChunk, DocumentChunk.id == RAGCitation.chunk_id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            RAGCitation.id == citation_id,
            RAGResponseRecord.workspace_id == workspace.id,
            Document.workspace_id == workspace.id,
        )
    ).one_or_none()
    if row is None:
        return None
    citation, _response, chunk, document = row
    return SourceReference(
        citation_id=citation.id,
        position=citation.position,
        document_id=document.id,
        chunk_id=chunk.id,
        filename=document.original_filename,
        page_number=chunk.page_number,
        similarity=citation.similarity,
        locator=chunk.content_unit.locator if chunk.content_unit is not None else None,
        extraction_method=(
            chunk.content_unit.extraction_method if chunk.content_unit is not None else None
        ),
    )


def get_responses(
    db: Session, workspace: Workspace, response_ids: list[UUID]
) -> dict[UUID, RAGResult]:
    """Resolve a batch of response/citation graphs inside one workspace boundary."""
    if not response_ids:
        return {}
    records = list(
        db.scalars(
            select(RAGResponseRecord).where(
                RAGResponseRecord.id.in_(response_ids),
                RAGResponseRecord.workspace_id == workspace.id,
            )
        ).all()
    )
    if not records:
        return {}
    record_ids = [record.id for record in records]
    rows = db.execute(
        select(RAGCitation, DocumentChunk, Document)
        .join(DocumentChunk, DocumentChunk.id == RAGCitation.chunk_id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            RAGCitation.response_id.in_(record_ids),
            Document.workspace_id == workspace.id,
        )
        .order_by(RAGCitation.response_id, RAGCitation.position)
    ).all()
    grouped: dict[UUID, list[tuple[RAGCitation, DocumentChunk, Document]]] = {
        record_id: [] for record_id in record_ids
    }
    for citation, chunk, document in rows:
        grouped[citation.response_id].append((citation, chunk, document))
    results: dict[UUID, RAGResult] = {}
    for record in records:
        evidence_rows = grouped[record.id]
        # Chunk/page/document deletion cascades citations. A once-grounded answer
        # is concealed if any original evidence is no longer available.
        if len(evidence_rows) != record.citation_count:
            continue
        sources = tuple(
            SourceReference(
                citation_id=citation.id,
                position=citation.position,
                document_id=document.id,
                chunk_id=chunk.id,
                filename=document.original_filename,
                page_number=chunk.page_number,
                similarity=citation.similarity,
                locator=chunk.content_unit.locator if chunk.content_unit is not None else None,
                extraction_method=(
                    chunk.content_unit.extraction_method
                    if chunk.content_unit is not None
                    else None
                ),
            )
            for citation, chunk, document in evidence_rows
        )
        results[record.id] = RAGResult(
            response_id=record.id,
            answer=record.answer,
            sources=sources,
            insufficient_evidence=record.insufficient_evidence,
            model=record.model,
        )
    return results
