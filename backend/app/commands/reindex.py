"""Re-indexing CLI management command for AURORA.

Usage:
    python -m app.commands.reindex --document <id> --dry-run
    python -m app.commands.reindex --document <id> --execute
    python -m app.commands.reindex --all --dry-run
    python -m app.commands.reindex --all --execute
"""

import argparse
import sys
import uuid
from pathlib import Path

# Ensure backend root is in python path
backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.document import Document
from app.embeddings.deps import get_embedding_provider
from app.services.indexing import ReindexStats, reindex_document


def print_stats_table(stats_list: list[ReindexStats]) -> None:
    headers = [
        "Filename",
        "Old Chunks",
        "New Chunks",
        "Old Avg",
        "New Avg",
        "Old <80",
        "New <80",
        "Status",
    ]
    row_fmt = "{:<35} | {:<10} | {:<10} | {:<8} | {:<8} | {:<8} | {:<8} | {:<8}"
    divider = "-" * 115

    print("\n" + "=" * 115)
    print("AURORA RE-INDEXING REPORT" + (" [DRY-RUN]" if all(s.dry_run for s in stats_list) else " [EXECUTED]"))
    print("=" * 115)
    print(row_fmt.format(*headers))
    print(divider)

    for s in stats_list:
        short_name = s.filename if len(s.filename) <= 35 else s.filename[:32] + "..."
        print(
            row_fmt.format(
                short_name,
                s.old_chunk_count,
                s.new_chunk_count,
                f"{s.old_avg_length:.1f}",
                f"{s.new_avg_length:.1f}",
                s.old_tiny_chunks,
                s.new_tiny_chunks,
                s.status,
            )
        )
        if s.error:
            print(f"  [ERROR] {s.error}")

    print("=" * 115 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="AURORA Resumable Re-indexing CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--document", type=str, help="Document UUID to re-index")
    group.add_argument("--all", action="store_true", help="Re-index all documents across all workspaces")

    parser.add_argument("--dry-run", action="store_true", default=True, help="Simulate re-indexing without changing DB (Default)")
    parser.add_argument("--execute", action="store_true", help="Commit new embeddings and atomically swap chunks in DB")
    parser.add_argument("--batch-size", type=int, default=20, help="Embedding batch size for rate-limit throttling (Default: 20)")

    args = parser.parse_args()
    is_dry_run = not args.execute

    db = SessionLocal()
    try:
        documents: list[Document] = []
        if args.document:
            try:
                doc_uuid = uuid.UUID(args.document)
            except ValueError:
                print(f"[ERROR] Invalid UUID: {args.document}", file=sys.stderr)
                return 1
            doc = db.scalar(select(Document).where(Document.id == doc_uuid))
            if not doc:
                print(f"[ERROR] Document not found: {args.document}", file=sys.stderr)
                return 1
            documents = [doc]
        else:
            documents = list(db.scalars(select(Document).where(Document.status == "PROCESSED").order_by(Document.created_at)).all())

        if not documents:
            print("[INFO] No processed documents found to re-index.")
            return 0

        print(f"[REINDEX] Found {len(documents)} document(s) to process. Mode: {'DRY RUN' if is_dry_run else 'EXECUTE'}")

        provider = None
        if not is_dry_run:
            provider = get_embedding_provider()

        results: list[ReindexStats] = []
        for doc in documents:
            print(f"[REINDEX] Analyzing '{doc.original_filename}' (ID: {doc.id})...")
            # If dry-run, provider is not called for embeddings
            stats = reindex_document(
                db=db,
                document=doc,
                provider=provider,  # type: ignore
                dry_run=is_dry_run,
                batch_size=args.batch_size,
            )
            results.append(stats)

        print_stats_table(results)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
