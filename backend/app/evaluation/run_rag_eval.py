"""Runnable evaluation script for the AURORA RAG pipeline.

Run as:
    python -m app.evaluation.run_rag_eval
    python -m app.evaluation.run_rag_eval --live
    python -m app.evaluation.run_rag_eval --json
"""

import argparse
import json
import os
import sys
from pathlib import Path
import uuid

# Ensure backend root is in python path
backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace import Workspace
from app.evaluation.rag_evaluator import (
    CategorySummary,
    EvalDeterministicEmbeddingProvider,
    EvalDeterministicLLMProvider,
    run_evaluation,
    seed_eval_workspace,
)


def print_table(summaries: list[CategorySummary]) -> None:
    headers = [
        "Category",
        "Cases",
        "Hit Rate %",
        "Facts Cov %",
        "Cite Acc %",
        "Refusal %",
        "Mean Latency (ms)",
        "LLM Calls",
    ]
    row_fmt = "{:<18} | {:<5} | {:<10} | {:<11} | {:<10} | {:<9} | {:<17} | {:<9}"
    divider = "-" * 105

    print("\n" + "=" * 105)
    print("AURORA RAG PIPELINE EVALUATION REPORT")
    print("=" * 105)
    print(row_fmt.format(*headers))
    print(divider)

    total_cases = sum(s.case_count for s in summaries)
    total_hit = sum(s.retrieval_hit_rate * s.case_count for s in summaries) / total_cases if total_cases else 0
    total_fact = sum(s.facts_coverage * s.case_count for s in summaries) / total_cases if total_cases else 0
    total_cite = sum(s.citation_accuracy * s.case_count for s in summaries) / total_cases if total_cases else 0
    total_refuse = sum(s.refusal_accuracy * s.case_count for s in summaries) / total_cases if total_cases else 0
    total_lat = sum(s.mean_latency_ms * s.case_count for s in summaries) / total_cases if total_cases else 0
    total_calls = sum(s.mean_llm_calls * s.case_count for s in summaries) / total_cases if total_cases else 0

    for s in summaries:
        print(
            row_fmt.format(
                s.category,
                s.case_count,
                f"{s.retrieval_hit_rate:.1f}%",
                f"{s.facts_coverage:.1f}%",
                f"{s.citation_accuracy:.1f}%",
                f"{s.refusal_accuracy:.1f}%",
                f"{s.mean_latency_ms:.1f}",
                f"{s.mean_llm_calls:.1f}",
            )
        )

    print(divider)
    print(
        row_fmt.format(
            "OVERALL BENCHMARK",
            total_cases,
            f"{total_hit:.1f}%",
            f"{total_fact:.1f}%",
            f"{total_cite:.1f}%",
            f"{total_refuse:.1f}%",
            f"{total_lat:.1f}",
            f"{total_calls:.1f}",
        )
    )
    print("=" * 105 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="AURORA RAG Pipeline Evaluation Harness")
    parser.add_argument("--live", action="store_true", help="Use real Gemini embedding and LLM providers")
    parser.add_argument("--json", action="store_true", help="Output summary in JSON format")
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(backend_dir / "tests" / "rag_eval" / "golden_dataset.json"),
        help="Path to golden evaluation dataset JSON",
    )
    args = parser.parse_args()

    embedding_provider = None
    llm_provider = None

    if args.live:
        from app.embeddings.gemini import GeminiEmbeddingProvider
        from app.llm.gemini import GeminiLLMProvider
        if not settings.GEMINI_API_KEY:
            print("[ERROR] GEMINI_API_KEY must be configured in .env for --live evaluation", file=sys.stderr)
            return 1
        embedding_provider = GeminiEmbeddingProvider()
        llm_provider = GeminiLLMProvider()
    else:
        embedding_provider = EvalDeterministicEmbeddingProvider()
        llm_provider = EvalDeterministicLLMProvider()

    db = SessionLocal()
    eval_workspace = None
    eval_user = None

    try:
        # Find or create evaluation user & isolated evaluation workspace
        eval_user = db.scalar(select(User).order_by(User.id).limit(1))
        if not eval_user:
            eval_user = User(
                email=f"eval_{uuid.uuid4().hex[:8]}@aurora.internal",
                password_hash="argon2id$mockhashforragtesting",
                display_name="RAG Evaluator",
                system_role="USER",
            )
            db.add(eval_user)
            db.flush()

        workspace_name = f"RAG-Eval-{uuid.uuid4().hex[:8]}"
        eval_workspace = Workspace(
            name=workspace_name,
            description="Ephemeral RAG evaluation workspace",
            created_by=eval_user.id,
        )
        db.add(eval_workspace)
        db.commit()
        db.refresh(eval_workspace)

        print(f"[EVAL] Setting up evaluation workspace '{eval_workspace.name}'...")
        print("[EVAL] Ingesting and indexing 4 fixture documents (slides, handbook, quiz CSV, resume)...")
        seed_eval_workspace(db, eval_workspace, eval_user, embedding_provider)

        print(f"[EVAL] Running 40 evaluation cases against dataset: {args.dataset}...")
        results, summaries = run_evaluation(
            db=db,
            workspace=eval_workspace,
            user=eval_user,
            dataset_path=args.dataset,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
            top_k=5,
        )

        if args.json:
            output = {
                "summaries": [s.__dict__ for s in summaries],
                "results": [r.__dict__ for r in results],
            }
            print(json.dumps(output, indent=2))
        else:
            print_table(summaries)

        return 0
    finally:
        # Clean up ephemeral evaluation workspace
        if eval_workspace:
            try:
                db.delete(eval_workspace)
                db.commit()
            except Exception:
                db.rollback()
        db.close()


if __name__ == "__main__":
    sys.exit(main())
