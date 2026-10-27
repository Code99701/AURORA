"""Integration tests for the RAG evaluation harness."""

from pathlib import Path
import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace import Workspace
from app.evaluation.rag_evaluator import (
    EvalDeterministicEmbeddingProvider,
    EvalDeterministicLLMProvider,
    run_evaluation,
    seed_eval_workspace,
)


DATASET_PATH = Path(__file__).parent / "rag_eval" / "golden_dataset.json"


@pytest.fixture
def eval_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_rag_evaluation_harness(eval_db: Session):
    user = User(
        email=f"rag_eval_tester_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="argon2id$mockhashforragtesting",
        display_name="Eval Tester",
        system_role="USER",
    )
    eval_db.add(user)
    eval_db.flush()

    workspace = Workspace(
        name=f"Eval Workspace {uuid.uuid4().hex[:8]}",
        created_by=user.id,
    )
    eval_db.add(workspace)
    eval_db.commit()
    eval_db.refresh(workspace)

    emb_provider = EvalDeterministicEmbeddingProvider()
    llm_provider = EvalDeterministicLLMProvider()

    # Seed the 4 documents
    docs = seed_eval_workspace(eval_db, workspace, user, emb_provider)
    assert len(docs) == 4
    assert "slides" in docs
    assert "handbook" in docs
    assert "quiz_csv" in docs
    assert "resume" in docs

    # Run evaluation
    results, summaries = run_evaluation(
        db=eval_db,
        workspace=workspace,
        user=user,
        dataset_path=str(DATASET_PATH),
        embedding_provider=emb_provider,
        llm_provider=llm_provider,
        top_k=5,
    )

    assert len(results) >= 40
    assert len(summaries) == 10

    # Ensure no unhandled exceptions in any evaluation case
    for r in results:
        assert r.error is None, f"Eval case {r.case_id} failed with error: {r.error}"

    # Verify summaries contain all required intent categories
    categories = {s.category for s in summaries}
    expected_categories = {
        "FACT",
        "PAGE_RANGE",
        "DOC_OVERVIEW",
        "SECTION_SUMMARY",
        "AGGREGATION",
        "COMPARISON",
        "MULTI_HOP",
        "FOLLOWUP",
        "HINDI",
        "UNANSWERABLE",
    }
    assert categories == expected_categories
