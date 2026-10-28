"""Re-indexing and Embedding Migration CLI for AURORA.

Usage:
    # Preview migration (Dry Run)
    python -m app.commands.reindex --all --dry-run
    python -m app.commands.reindex --document <id> --dry-run

    # Execute migration with automatic recovery manifest creation
    python -m app.commands.reindex --all --execute
    python -m app.commands.reindex --all --execute --resume

    # Roll back from a recovery manifest
    python -m app.commands.reindex --rollback <path/to/manifest.json>
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
from app.services.embedding_migration import (
    MigrationResult,
    migrate_document_embeddings,
    restore_embeddings_from_manifest,
)


def print_migration_table(results: list[MigrationResult]) -> None:
    headers = [
        "Filename",
        "Old Model",
        "New Model",
        "Chunks",
        "In-Place",
        "Status",
    ]
    row_fmt = "{:<32} | {:<22} | {:<22} | {:<8} | {:<8} | {:<10}"
    divider = "-" * 115

    print("\n" + "=" * 115)
    print("AURORA EMBEDDING MIGRATION REPORT" + (" [DRY-RUN]" if all(r.status == "DRY_RUN" for r in results) else " [EXECUTED]"))
    print("=" * 115)
    print(row_fmt.format(*headers))
    print(divider)

    for r in results:
        short_name = r.filename if len(r.filename) <= 32 else r.filename[:29] + "..."
        old_m = (r.old_model or "none")[:22]
        new_m = (r.new_model or "none")[:22]
        print(
            row_fmt.format(
                short_name,
                old_m,
                new_m,
                r.chunk_count,
                "YES" if r.in_place_updated else "NO",
                r.status,
            )
        )
        if r.backup_path:
            print(f"  [BACKUP MANIFEST] {r.backup_path}")
        if r.error:
            print(f"  [ERROR] {r.error}")

    print("=" * 115 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="AURORA Resumable Embedding Migration & Re-indexing CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--document", type=str, help="Document UUID to migrate")
    group.add_argument("--all", action="store_true", help="Migrate all processed documents")
    group.add_argument("--rollback", type=str, help="Path to recovery manifest JSON to restore from")

    parser.add_argument("--dry-run", action="store_true", default=True, help="Simulate migration without modifying DB (Default)")
    parser.add_argument("--execute", action="store_true", help="Execute embedding migration and commit to DB")
    parser.add_argument("--resume", action="store_true", help="Skip documents already migrated to the active provider model")
    parser.add_argument("--batch-size", type=int, default=20, help="Embedding batch size (Default: 20)")
    parser.add_argument("--provider", type=str, choices=["local"], default="local", help="Embedding provider (local)")
    parser.add_argument("--allow-rechunk", action="store_true", help="Allow destructive chunk replacement if structural identity fails")
    parser.add_argument("--no-backup", action="store_true", help="Disable creation of recovery manifests")

    args = parser.parse_args()
    is_dry_run = not args.execute

    db = SessionLocal()
    try:
        # Handle Rollback Mode
        if args.rollback:
            print(f"[ROLLBACK] Restoring embeddings from manifest: {args.rollback}")
            try:
                res = restore_embeddings_from_manifest(db, args.rollback)
                print(f"[ROLLBACK SUCCESS] Restored document '{res['filename']}' ({res['restored_chunks']} chunks) to model '{res['restored_model']}'.")
                return 0
            except Exception as exc:
                print(f"[ROLLBACK ERROR] Restore failed: {exc}", file=sys.stderr)
                return 1

        # Handle Migration Mode
        from app.embeddings.local import LocalEmbeddingProvider
        from app.core.config import settings

        if args.provider == "local":
            provider = LocalEmbeddingProvider(
                model_name=settings.LOCAL_EMBEDDING_MODEL,
                dimension=settings.EMBEDDING_DIMENSION,
                device=settings.LOCAL_EMBEDDING_DEVICE,
                batch_size=settings.LOCAL_EMBEDDING_BATCH_SIZE,
                cache_size=settings.LOCAL_EMBEDDING_CACHE_SIZE,
            )
        else:
            provider = get_embedding_provider()
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
            documents = list(
                db.scalars(
                    select(Document)
                    .where(Document.status.in_(["PROCESSED", "PARTIALLY_PROCESSED"]))
                    .order_by(Document.created_at)
                ).all()
            )

        if not documents:
            print("[INFO] No processed documents found to migrate.")
            return 0

        print(
            f"[MIGRATION] Found {len(documents)} document(s). Target Model: '{provider.model_name}'. "
            f"Mode: {'DRY RUN' if is_dry_run else 'EXECUTE'}"
        )

        results: list[MigrationResult] = []
        for doc in documents:
            if args.resume and doc.embedding_model == provider.model_name and doc.indexing_status == "INDEXED":
                print(f"[SKIP] '{doc.original_filename}' is already indexed with '{provider.model_name}'.")
                continue

            print(f"[MIGRATION] Analyzing '{doc.original_filename}' (ID: {doc.id})...")
            res = migrate_document_embeddings(
                db=db,
                document=doc,
                provider=provider,
                dry_run=is_dry_run,
                batch_size=args.batch_size,
                allow_rechunk=args.allow_rechunk,
                backup=not args.no_backup,
            )
            results.append(res)

        print_migration_table(results)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
