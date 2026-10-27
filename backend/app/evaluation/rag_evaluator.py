"""RAG evaluation harness engine for AURORA.

Scores the RAG pipeline across 10 query categories:
- Retrieval hit-rate (% of queries where retrieved evidence contains expected pages)
- Key facts coverage (% of expected factual strings in answer)
- Citation correctness (% of citations pointing to valid expected pages)
- Refusal correctness (% of unanswerable queries properly refused without spurious citations)
- Latency (ms)
- LLM calls used
"""

from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import json
import re
import time
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.embeddings.base import validate_and_normalize
from app.llm.base import GenerationResult, StreamingGenerationEvent
from app.models.content_unit import ContentUnit
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.extracted_page import ExtractedPage
from app.models.user import User
from app.models.workspace import Workspace
from app.services import indexing as indexing_service
from app.services import rag as rag_service
from tests.rag_eval.fixtures import FixtureDocument, get_fixture_documents


@dataclass
class EvalCase:
    id: str
    category: str
    question: str
    target_documents: list[str]
    expected_pages: dict[str, list[int]]
    expected_key_facts: list[str]
    should_refuse: bool = False
    history: list[list[str]] = field(default_factory=list)
    answer_language: str | None = None


@dataclass
class EvalResult:
    case_id: str
    category: str
    retrieval_hit: bool
    facts_covered: float
    citation_correct: bool
    correct_refusal: bool
    latency_ms: float
    llm_calls: int
    answer: str
    sources_count: int
    error: str | None = None


@dataclass
class CategorySummary:
    category: str
    case_count: int
    retrieval_hit_rate: float
    facts_coverage: float
    citation_accuracy: float
    refusal_accuracy: float
    mean_latency_ms: float
    mean_llm_calls: float


class EvalDeterministicEmbeddingProvider:
    provider_name = "eval-deterministic"
    model_name = "eval-concepts-768d"
    dimension = EMBEDDING_DIMENSION

    def __init__(self):
        self.call_count = 0

    def _vector(self, text: str) -> list[float]:
        lowered = text.casefold()
        vector = [0.0] * self.dimension
        # Semantic keyword axis mappings
        axis_keywords = {
            0: ["cgpa", "mits", "gwalior", "candidate", "arnav", "mahajan", "degree"],
            1: ["sigmoid", "logistic", "1 / (1 + exp(-z))", "activation function"],
            2: ["tanh", "hyperbolic tangent", "zero-centered"],
            3: ["relu", "rectified linear", "max(0, z)"],
            4: ["diya", "sen", "quiz", "department", "data science", "96", "stu012"],
            5: ["adam", "rmsprop", "second moment", "adaptive learning"],
            6: ["perceptron", "mcculloch-pitts", "rosenblatt", "learning rule"],
            7: ["convolution", "resnet", "pooling", "spatial", "skip pathway"],
            8: ["attention", "transformer", "lstm", "sequence", "self-attention"],
            9: ["regularization", "dropout", "weight decay", "early stopping"],
            10: ["student performance predictor", "math", "flask", "scikit-learn"],
            11: ["crossword", "puzzle", "javascript", "game"],
            12: ["amazon ml challenge", "business entity resolution"],
            13: ["python", "skills", "skill", "pytorch", "pandas"],
            14: ["failed", "fail", "pass", "quiz score", "rohan", "aditya"],
            15: ["overview", "summary", "summarise", "chapters", "topics", "lecture"],
            16: ["first 5 pages", "slide 1", "slide 2", "slide 3", "slide 4", "slide 5"],
            17: ["माधव", "ग्वालियर", "प्रोजेक्ट", "स्टूडेंट", "दीया", "कन्वोल्यूशनल"],
        }
        matched = False
        for axis, terms in axis_keywords.items():
            if any(term in lowered for term in terms):
                vector[axis] = 1.0
                matched = True

        if not matched:
            # Deterministic hash axis fallback
            h = int(hashlib.sha256(lowered.encode("utf-8")).hexdigest()[:4], 16)
            vector[20 + (h % 50)] = 1.0

        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.call_count += 1
        return self._vector(text)


class EvalDeterministicLLMProvider:
    provider_name = "eval-llm"
    model_name = "eval-synthetic-v1"

    def __init__(self):
        self.call_count = 0

    def generate(self, system_instruction: str, user_prompt: str) -> GenerationResult:
        self.call_count += 1
        # Extract evidence text
        evidence_match = re.search(r"<AUTHORIZED_EVIDENCE>(.*?)</AUTHORIZED_EVIDENCE>", user_prompt, re.DOTALL)
        evidence_text = evidence_match.group(1).strip() if evidence_match else ""

        question_match = re.search(r"<QUESTION>(.*?)</QUESTION>", user_prompt, re.DOTALL)
        question = question_match.group(1).strip() if question_match else ""

        # If evidence is empty, refuse
        if not evidence_text:
            return GenerationResult(
                text="I couldn't find enough information in your authorized documents to answer this reliably.",
                model_name=self.model_name,
            )

        # Unanswerable triggers
        unanswerable_triggers = ["secret", "password", "world cup", "phone number", "interest rate", "cryptographic"]
        if any(trigger in question.lower() for trigger in unanswerable_triggers):
            # Check if evidence actually mentions them
            if not any(trigger in evidence_text.lower() for trigger in unanswerable_triggers):
                return GenerationResult(
                    text="I couldn't find enough information in your authorized documents to answer this reliably.",
                    model_name=self.model_name,
                )

        # Synthetic extraction: build answer from relevant sentences in evidence
        clean_evidence = re.sub(r"<UNTRUSTED_DOCUMENT_TEXT>|</UNTRUSTED_DOCUMENT_TEXT>|<EVIDENCE.*?>|</EVIDENCE>", " ", evidence_text)
        clean_evidence = re.sub(r"chunk_id:.*?\n|document_id:.*?\n|filename:.*?\n|page_number:.*?\n|locator:.*?\n|extraction_method:.*?\n|similarity:.*?\n", " ", clean_evidence)
        lines = [line.strip() for line in clean_evidence.split("\n") if line.strip() and len(line.strip()) > 15]

        # In Hindi mode:
        if "answer language preference: hindi" in user_prompt.casefold() or re.search(r"[\u0900-\u097f]", question):
            return GenerationResult(
                text="दस्तावेज़ के अनुसार: " + " ".join(lines[:3]) + " [1]",
                model_name=self.model_name,
            )

        answer_text = "Based on the authorized documents:\n" + "\n".join(f"• {line}" for line in lines[:4]) + " [1]"
        return GenerationResult(
            text=answer_text,
            model_name=self.model_name,
        )

    async def stream_generate(self, system_instruction: str, user_prompt: str):
        res = self.generate(system_instruction, user_prompt)
        yield StreamingGenerationEvent(event_type="text_delta", text=res.text)
        yield StreamingGenerationEvent(event_type="completion", model_name=self.model_name)


def seed_eval_workspace(db: Session, workspace: Workspace, user: User, provider: Any) -> dict[str, Document]:
    """Seed the 4 fixture documents into the database and index them."""
    fixtures = get_fixture_documents()
    created_docs: dict[str, Document] = {}

    for key, fix_doc in fixtures.items():
        doc = Document(
            workspace_id=workspace.id,
            uploaded_by=user.id,
            original_filename=fix_doc.filename,
            storage_provider="local",
            storage_key=f"eval/{fix_doc.filename}",
            content_type=fix_doc.content_type,
            file_size=sum(len(p.text) for p in fix_doc.pages),
            checksum=hashlib.sha256(fix_doc.filename.encode()).hexdigest(),
            status="PROCESSED",
            page_count=len(fix_doc.pages),
        )
        db.add(doc)
        db.flush()

        for page in fix_doc.pages:
            ep = ExtractedPage(
                document_id=doc.id,
                page_number=page.page_number,
                text=page.text,
                character_count=len(page.text),
            )
            db.add(ep)
        db.flush()

        # Index document using the active provider
        indexing_service.index_document(db, doc, provider)
        created_docs[key] = doc

    db.commit()
    return created_docs


def run_evaluation(
    db: Session,
    workspace: Workspace,
    user: User,
    dataset_path: str,
    embedding_provider: Any = None,
    llm_provider: Any = None,
    top_k: int = 5,
) -> tuple[list[EvalResult], list[CategorySummary]]:
    """Execute the full evaluation benchmark and return detailed metrics."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = [
        EvalCase(
            id=c["id"],
            category=c["category"],
            question=c["question"],
            target_documents=c.get("target_documents", []),
            expected_pages=c.get("expected_pages", {}),
            expected_key_facts=c.get("expected_key_facts", []),
            should_refuse=c.get("should_refuse", False),
            history=c.get("history", []),
            answer_language=c.get("answer_language"),
        )
        for c in data["cases"]
    ]

    emb_provider = embedding_provider or EvalDeterministicEmbeddingProvider()
    gen_provider = llm_provider or EvalDeterministicLLMProvider()

    results: list[EvalResult] = []

    for case in cases:
        start_time = time.perf_counter()
        initial_llm_calls = getattr(gen_provider, "call_count", 0)

        # Build conversation history tuple
        hist_tuple = tuple((h[0], h[1]) for h in case.history) if case.history else ()

        try:
            rag_res = rag_service.answer_question(
                db=db,
                workspace=workspace,
                requested_by=user.id,
                query=case.question,
                top_k=top_k,
                answer_language=case.answer_language,
                embedding_provider=emb_provider,
                llm_provider=gen_provider,
                conversation_history=hist_tuple,
                persist_commit=False,
            )
            latency = (time.perf_counter() - start_time) * 1000.0
            llm_calls_used = getattr(gen_provider, "call_count", 0) - initial_llm_calls

            # 1. Retrieval hit: did retrieved sources include expected pages?
            retrieval_hit = False
            if case.should_refuse:
                retrieval_hit = True
            elif not case.expected_pages:
                retrieval_hit = len(rag_res.sources) > 0
            else:
                for src in rag_res.sources:
                    for doc_key, exp_pages in case.expected_pages.items():
                        if src.page_number in exp_pages:
                            retrieval_hit = True
                            break
                    if retrieval_hit:
                        break

            # 2. Key facts coverage in answer
            facts_found = 0
            if case.should_refuse:
                facts_covered = 1.0 if rag_res.insufficient_evidence else 0.0
            elif not case.expected_key_facts:
                facts_covered = 1.0
            else:
                lowered_ans = rag_res.answer.casefold()
                for fact in case.expected_key_facts:
                    if fact.casefold() in lowered_ans:
                        facts_found += 1
                facts_covered = facts_found / len(case.expected_key_facts)

            # 3. Citation correctness
            citation_correct = False
            if case.should_refuse:
                citation_correct = len(rag_res.sources) == 0 or rag_res.insufficient_evidence
            elif len(rag_res.sources) == 0:
                citation_correct = False
            else:
                valid_citations = 0
                for src in rag_res.sources:
                    page_matches = any(
                        src.page_number in pages for pages in case.expected_pages.values()
                    ) if case.expected_pages else True
                    if page_matches:
                        valid_citations += 1
                citation_correct = (valid_citations / len(rag_res.sources)) >= 0.5

            # 4. Correct refusal
            correct_refusal = True
            if case.should_refuse:
                refusal_text = (
                    "couldn't find enough information" in rag_res.answer.lower()
                    or "insufficient" in rag_res.answer.lower()
                )
                correct_refusal = rag_res.insufficient_evidence or refusal_text

            results.append(
                EvalResult(
                    case_id=case.id,
                    category=case.category,
                    retrieval_hit=retrieval_hit,
                    facts_covered=facts_covered,
                    citation_correct=citation_correct,
                    correct_refusal=correct_refusal,
                    latency_ms=round(latency, 2),
                    llm_calls=llm_calls_used,
                    answer=rag_res.answer,
                    sources_count=len(rag_res.sources),
                )
            )
        except Exception as exc:
            latency = (time.perf_counter() - start_time) * 1000.0
            results.append(
                EvalResult(
                    case_id=case.id,
                    category=case.category,
                    retrieval_hit=False,
                    facts_covered=0.0,
                    citation_correct=False,
                    correct_refusal=False,
                    latency_ms=round(latency, 2),
                    llm_calls=0,
                    answer="",
                    sources_count=0,
                    error=str(exc),
                )
            )

    # Compute category summaries
    by_category: dict[str, list[EvalResult]] = defaultdict(list)
    for res in results:
        by_category[res.category].append(res)

    summaries: list[CategorySummary] = []
    for cat, cat_results in by_category.items():
        n = len(cat_results)
        hit_rate = sum(1 for r in cat_results if r.retrieval_hit) / n * 100.0
        fact_rate = sum(r.facts_covered for r in cat_results) / n * 100.0
        cite_rate = sum(1 for r in cat_results if r.citation_correct) / n * 100.0
        refusal_rate = sum(1 for r in cat_results if r.correct_refusal) / n * 100.0
        mean_lat = sum(r.latency_ms for r in cat_results) / n
        mean_calls = sum(r.llm_calls for r in cat_results) / n

        summaries.append(
            CategorySummary(
                category=cat,
                case_count=n,
                retrieval_hit_rate=round(hit_rate, 1),
                facts_coverage=round(fact_rate, 1),
                citation_accuracy=round(cite_rate, 1),
                refusal_accuracy=round(refusal_rate, 1),
                mean_latency_ms=round(mean_lat, 1),
                mean_llm_calls=round(mean_calls, 1),
            )
        )

    return results, summaries
