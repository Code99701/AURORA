"""Tests for General Query Understanding & Intelligent RAG Improvement in AURORA.

Covers:
1. Direct factual questions and core subject extraction.
2. Dynamic document targeting and alias matching (exact, stem, aliases like 'resume', 'ann ppt', 'ml book').
3. Cross-document comparisons with balanced candidate retrieval across multiple documents.
4. Document overview vs topic-specific summaries.
5. Information extraction and structured listing.
6. Multilingual requests and Hindi translation.
7. Conversational follow-ups (pronoun, comparison, location, simplification, detail, ordinal, bullet, context boundary).
8. Page and slide constraints (PDF pages, PPTX slide numbers).
9. Honest refusal and missing evidence handling with zero bogus citations.
10. Workspace isolation and prompt task guidance.
"""

from dataclasses import dataclass
import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.llm.base import GenerationResult
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.models.content_unit import ContentUnit
from app.models.workspace import Workspace
from app.rag.understanding import (
    PageSlideConstraint,
    QueryIntent,
    extract_page_or_slide_constraint,
    resolve_target_documents,
    understand_query,
)
from app.rag.rewriter import (
    RewriteResult,
    extract_core_subject,
    extract_numbered_items,
    rewrite_query_for_retrieval,
)
from app.rag.prompt import build_grounded_prompt
from app.services import rag as rag_service
from app.services.retrieval import (
    RetrievedChunk,
    _diversify_candidates,
    search_workspace,
)


# ---------------------------------------------------------------------------
# Test Fakes & Fixtures
# ---------------------------------------------------------------------------

class FakeDoc:
    def __init__(self, original_filename: str, doc_id: UUID | None = None):
        self.id = doc_id or uuid.uuid4()
        self.original_filename = original_filename


class FakeEmbeddingProvider:
    provider_name = "fake"
    model_name = "intfloat/multilingual-e5-base"
    dimension = EMBEDDING_DIMENSION

    def embed_documents(self, texts):
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, text):
        return [0.0] * self.dimension


# ---------------------------------------------------------------------------
# 1. Direct Factual & Core Subject Extraction Tests
# ---------------------------------------------------------------------------

def test_understand_factual_query():
    query = "What is the chunk size and embedding dimension used in the AURORA project?"
    intent = understand_query(query)
    assert intent.task == "FACTUAL"
    assert "chunk size" in intent.search_query.casefold()
    assert intent.target_language is None
    assert intent.page_slide_constraint is None


def test_core_subject_extraction():
    q1 = "Can you please tell me about the architecture of AURORA?"
    subj1 = extract_core_subject(q1)
    assert "architecture of aurora" in subj1.casefold()

    q2 = "What are the key differences between CNN and RNN?"
    subj2 = extract_core_subject(q2)
    assert "key differences between cnn and rnn" in subj2.casefold()


# ---------------------------------------------------------------------------
# 2. Dynamic Document Targeting & Alias Matching Tests
# ---------------------------------------------------------------------------

def test_dynamic_document_alias_matching():
    doc_resume = FakeDoc("Arnav_Mahajan_Resume.pdf")
    doc_ann = FakeDoc("ANN PPT UNIT 2.pdf")
    doc_ml = FakeDoc("the-hundred-page-machine-learning-book_compress.pdf")
    doc_report = FakeDoc("Sample_Report for MAC Department for all.pdf")
    docs = [doc_resume, doc_ann, doc_ml, doc_report]

    # Exact filename match
    m1 = resolve_target_documents("check Arnav_Mahajan_Resume.pdf", docs)
    assert len(m1) == 1
    assert m1[0].document_id == doc_resume.id

    # Natural alias 'resume'
    m2 = resolve_target_documents("what skills appear on the resume?", docs)
    assert len(m2) == 1
    assert m2[0].document_id == doc_resume.id

    # Natural alias 'ann ppt' or 'ann presentation'
    m3 = resolve_target_documents("what is covered in the ann ppt?", docs)
    assert len(m3) == 1
    assert m3[0].document_id == doc_ann.id

    # Natural alias 'ml book' or 'machine learning book'
    m4 = resolve_target_documents("who coined the term machine learning in the ml book?", docs)
    assert len(m4) == 1
    assert m4[0].document_id == doc_ml.id

    # Multi-word alias 'sample report'
    m5 = resolve_target_documents("summarise the findings in the sample report", docs)
    assert len(m5) == 1
    assert m5[0].document_id == doc_report.id


# ---------------------------------------------------------------------------
# 3. Cross-Document Comparisons & Balanced Retrieval Tests
# ---------------------------------------------------------------------------

def test_cross_document_comparison_intent():
    doc_ann = FakeDoc("ANN PPT UNIT 2.pdf")
    doc_ml = FakeDoc("the-hundred-page-machine-learning-book_compress.pdf")
    docs = [doc_ann, doc_ml]

    query = "Compare the neural network definition in ANN PPT with the ML book"
    intent = understand_query(query, docs)
    assert intent.task == "COMPARISON"
    assert intent.is_multi_document is True
    assert len(intent.target_documents) == 2
    matched_ids = {m.document_id for m in intent.target_documents}
    assert doc_ann.id in matched_ids
    assert doc_ml.id in matched_ids


def test_balanced_retrieval_diversification():
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()

    # 4 candidates from doc1 with high similarity, 4 from doc2 with slightly lower
    candidates = [
        RetrievedChunk(uuid.uuid4(), doc1_id, "doc1.pdf", 1, "text doc1 a", 0.95),
        RetrievedChunk(uuid.uuid4(), doc1_id, "doc1.pdf", 2, "text doc1 b", 0.94),
        RetrievedChunk(uuid.uuid4(), doc1_id, "doc1.pdf", 3, "text doc1 c", 0.93),
        RetrievedChunk(uuid.uuid4(), doc1_id, "doc1.pdf", 4, "text doc1 d", 0.92),
        RetrievedChunk(uuid.uuid4(), doc2_id, "doc2.pdf", 1, "text doc2 a", 0.88),
        RetrievedChunk(uuid.uuid4(), doc2_id, "doc2.pdf", 2, "text doc2 b", 0.87),
        RetrievedChunk(uuid.uuid4(), doc2_id, "doc2.pdf", 3, "text doc2 c", 0.86),
        RetrievedChunk(uuid.uuid4(), doc2_id, "doc2.pdf", 4, "text doc2 d", 0.85),
    ]

    # Prioritize both doc1 and doc2 for comparison
    balanced = _diversify_candidates(candidates, top_k=4, priority_doc_ids=[doc1_id, doc2_id])
    assert len(balanced) == 4
    # Round robin guarantees both doc1 and doc2 are present
    doc_ids = [c.document_id for c in balanced]
    assert doc1_id in doc_ids
    assert doc2_id in doc_ids
    assert doc_ids.count(doc1_id) == 2
    assert doc_ids.count(doc2_id) == 2


# ---------------------------------------------------------------------------
# 4. Document Overview vs Topic Summaries
# ---------------------------------------------------------------------------

def test_document_overview_vs_topic_summary():
    doc = FakeDoc("ANN PPT UNIT 2.pdf")

    # Document Overview
    q_overview = "Give me an overview of this presentation"
    intent_overview = understand_query(q_overview, [doc])
    assert intent_overview.task == "DOCUMENT_OVERVIEW"
    assert intent_overview.is_overview is True

    # Topic-specific summary should NOT be whole-document overview
    q_topic = "Summarise the biological neuron parts mentioned in the presentation"
    intent_topic = understand_query(q_topic, [doc])
    assert intent_topic.task == "TOPIC_SUMMARY"
    assert intent_topic.is_overview is False
    assert "neuron" in intent_topic.search_query.casefold()


# ---------------------------------------------------------------------------
# 5. Information Extraction & Listing Tests
# ---------------------------------------------------------------------------

def test_information_extraction_intent():
    q = "List all three projects detailed on the resume"
    intent = understand_query(q)
    assert intent.task == "EXTRACTION"
    assert intent.task_guidance is not None
    assert "list" in intent.task_guidance.casefold()


# ---------------------------------------------------------------------------
# 6. Multilingual & Translation Requests
# ---------------------------------------------------------------------------

def test_translation_intent():
    q1 = "Translate that into Hindi"
    intent1 = understand_query(q1)
    assert intent1.task == "TRANSLATION"
    assert intent1.target_language == "Hindi"

    q2 = "Explain this in Hindi me samjhao"
    intent2 = understand_query(q2)
    assert intent2.target_language == "Hindi"

    q3 = "हिंदी में अनुवाद करें"
    intent3 = understand_query(q3)
    assert intent3.target_language == "Hindi"


# ---------------------------------------------------------------------------
# 7. Conversational Follow-Ups & Disambiguation Tests
# ---------------------------------------------------------------------------

def test_conversational_followup_pronoun():
    history = (
        ("user", "What is an Artificial Neural Network?"),
        ("assistant", "An Artificial Neural Network is a computational model inspired by the human brain."),
    )
    res = rewrite_query_for_retrieval("What are its key advantages?", history)
    assert res.is_follow_up is True
    assert "artificial neural network" in res.rewritten_query.casefold()
    assert "advantages" in res.rewritten_query.casefold()


def test_conversational_followup_comparison():
    history = (
        ("user", "What is the biological neuron model in ANN PPT?"),
        ("assistant", "A biological neuron consists of dendrites, a soma, and an axon."),
    )
    res = rewrite_query_for_retrieval("Now compare it with the ML book", history)
    assert res.is_follow_up is True
    assert "compare" in res.rewritten_query.casefold()
    assert "ml book" in res.rewritten_query.casefold()


def test_conversational_followup_location():
    history = (
        ("user", "Explain supervised learning"),
        ("assistant", "Supervised learning uses labeled data."),
    )
    res = rewrite_query_for_retrieval("Where exactly is this mentioned?", history)
    assert res.is_follow_up is True
    assert "where" in res.rewritten_query.casefold()
    assert "mentioned" in res.rewritten_query.casefold()
    assert "supervised learning" in res.rewritten_query.casefold()


def test_conversational_followup_detail_and_simplification():
    history = (
        ("user", "What is gradient descent?"),
        ("assistant", "Gradient descent is an optimization algorithm used to minimize loss."),
    )
    res_more = rewrite_query_for_retrieval("Give me more details", history)
    assert res_more.is_follow_up is True
    assert "gradient descent" in res_more.rewritten_query.casefold()

    res_simple = rewrite_query_for_retrieval("Explain it more simply", history)
    assert res_simple.is_follow_up is True
    assert "gradient descent" in res_simple.rewritten_query.casefold()


def test_conversational_followup_numbered_and_bullet_references():
    # Numbered
    history_num = (
        ("user", "What are the types of machine learning?"),
        ("assistant", "1. Supervised Learning\n2. Unsupervised Learning\n3. Reinforcement Learning"),
    )
    res1 = rewrite_query_for_retrieval("Explain the second one", history_num)
    assert res1.is_follow_up is True
    assert "unsupervised learning" in res1.rewritten_query.casefold()

    # Bulleted
    history_bullet = (
        ("user", "What are the key components?"),
        ("assistant", "- **Dendrites**: Receive signals\n- **Soma**: Processes signals\n- **Axon**: Transmits signals"),
    )
    res2 = rewrite_query_for_retrieval("Tell me more about the 1st one", history_bullet)
    assert res2.is_follow_up is True
    assert "dendrites" in res2.rewritten_query.casefold()


def test_context_boundary_protection():
    history = (
        ("user", "What is the candidate's CGPA in the resume?"),
        ("assistant", "The candidate's CGPA is 7.3 according to the resume."),
    )
    # Self-contained question about a completely different topic/document
    res = rewrite_query_for_retrieval(
        "Who coined the term machine learning in 1959 according to the ML book?",
        history,
    )
    # Must NOT contaminate with CGPA or resume
    assert res.is_follow_up is False
    assert "cgpa" not in res.rewritten_query.casefold()
    assert "resume" not in res.rewritten_query.casefold()
    assert "1959" in res.rewritten_query


# ---------------------------------------------------------------------------
# 8. Structural Page & Slide Constraint Tests
# ---------------------------------------------------------------------------

def test_page_and_slide_constraints():
    # Pages
    c1 = extract_page_or_slide_constraint("explain first 5 pages of the pdf")
    assert c1 is not None
    assert (c1.start, c1.end, c1.unit) == (1, 5, "page")

    c2 = extract_page_or_slide_constraint("read pages 3 to 7")
    assert c2 is not None
    assert (c2.start, c2.end, c2.unit) == (3, 7, "page")

    c3 = extract_page_or_slide_constraint("what is on p. 4?")
    assert c3 is not None
    assert (c3.start, c3.end, c3.unit) == (4, 4, "page")

    # Slides
    c4 = extract_page_or_slide_constraint("what is on slide 8 of the presentation?")
    assert c4 is not None
    assert (c4.start, c4.end, c4.unit) == (8, 8, "slide")

    c5 = extract_page_or_slide_constraint("summarise slides 2 to 5")
    assert c5 is not None
    assert (c5.start, c5.end, c5.unit) == (2, 5, "slide")

    c6 = extract_page_or_slide_constraint("review first 3 slides")
    assert c6 is not None
    assert (c6.start, c6.end, c6.unit) == (1, 3, "slide")


# ---------------------------------------------------------------------------
# 9. Honest Refusal & Grounding Tests
# ---------------------------------------------------------------------------

def test_is_model_refusal_detection():
    # English refusals
    assert rag_service.is_model_refusal(
        "I couldn't find enough information in your authorized documents to answer this reliably."
    ) is True
    assert rag_service.is_model_refusal(
        "The provided documents do not contain any information about ice cream."
    ) is True
    assert rag_service.is_model_refusal(
        "The retrieved evidence does not mention the requested topic."
    ) is True

    # Hindi refusals
    assert rag_service.is_model_refusal(
        "उपलब्ध दस्तावेज़ों में इसके बारे में पर्याप्त जानकारी नहीं मिली।"
    ) is True

    # Non-refusals
    assert rag_service.is_model_refusal(
        "Arthur Samuel coined the term machine learning at IBM in 1959."
    ) is False


def test_grounded_prompt_with_task_guidance():
    prompt = build_grounded_prompt(
        question="Compare supervised and unsupervised learning",
        context="Supervised uses labels. Unsupervised finds patterns in unlabeled data.",
        answer_language="English",
        task_guidance="Provide a structured, balanced comparison.",
    )
    assert "TASK GUIDANCE" in prompt.user_prompt
    assert "balanced comparison" in prompt.user_prompt
    assert "Supervised uses labels" in prompt.user_prompt
    assert "AURORA, a document-grounded research assistant" in prompt.system_instruction
