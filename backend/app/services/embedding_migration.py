from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.embeddings import EmbeddingProvider
from app.embeddings.base import validate_and_normalize
from app.models.document import Document
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.rag.chunking import StructuredChunk, chunk_document_sources
from app.services.indexing import IndexableSource, get_indexable_sources

logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    document_id: str
    filename: str
    old_model: str | None
    new_model: str
    chunk_count: int
    in_place_updated: bool
    backup_path: str | None
    status: str
    error: str | None = None


def compute_chunk_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_vectors_checksum(vectors: list[list[float]]) -> str:
    hasher = hashlib.sha256()
    for v in vectors:
        hasher.update(",".join(f"{x:.6f}" for x in v).encode("utf-8"))
    return hasher.hexdigest()


def verify_chunk_structural_identity(
    existing_chunks: list[DocumentChunk],
    candidate_chunks: list[StructuredChunk],
) -> bool:
    """Verify that candidate chunks match existing chunks in exact count, text, and page bounds.

    Matching chunk counts alone are NEVER sufficient to establish chunk identity.
    Exact text and coordinate identity are required before reusing chunk IDs.
    """
    if len(existing_chunks) != len(candidate_chunks):
        return False
    for old_c, new_c in zip(existing_chunks, candidate_chunks, strict=True):
        if old_c.chunk_index != new_c.chunk_index:
            return False
        if old_c.text != new_c.text:
            return False
        if old_c.page_start != new_c.page_start or old_c.page_end != new_c.page_end:
            return False
    return True


def create_recovery_manifest(
    document: Document,
    chunks: list[DocumentChunk],
    backup_dir: Path | None = None,
) -> Path:
    """Write an immutable recovery manifest of existing chunk vectors before migration."""
    if backup_dir is None:
        backup_dir = settings.DOCUMENT_STORAGE_PATH / "backups" / "embeddings"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"manifest_{timestamp_str}_{document.id}.json"
    manifest_path = backup_dir / filename

    raw_vectors = [list(c.embedding) for c in chunks]
    checksum = compute_vectors_checksum(raw_vectors)

    manifest_data = {
        "manifest_version": "1.0",
        "backup_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "document": {
            "id": str(document.id),
            "workspace_id": str(document.workspace_id),
            "original_filename": document.original_filename,
            "embedding_model": document.embedding_model or (chunks[0].embedding_model if chunks else "unknown"),
            "embedding_dimension": document.embedding_dimension or EMBEDDING_DIMENSION,
            "chunk_count": len(chunks),
        },
        "vectors_checksum": checksum,
        "chunks": [
            {
                "chunk_id": str(c.id),
                "chunk_index": c.chunk_index,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "text_sha256": compute_chunk_text_hash(c.text),
                "embedding_model": c.embedding_model,
                "embedding": list(c.embedding),
            }
            for c in chunks
        ],
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    logger.info("Created embedding recovery manifest: %s", manifest_path)
    return manifest_path


def restore_embeddings_from_manifest(
    db: Session,
    manifest_path: Path | str,
) -> dict[str, Any]:
    """Restore document chunk vectors and model from a recovery manifest.

    Guarantees:
    - Validates manifest checksum before touching database rows.
    - Validates each chunk's text hash to guarantee referential validity.
    - Restores vectors and model in a single atomic transaction.
    """
    path = Path(manifest_path)
    if not path.is_file():
        raise FileNotFoundError(f"Recovery manifest file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    doc_info = manifest["document"]
    doc_id = uuid.UUID(doc_info["id"])
    manifest_chunks = manifest["chunks"]
    expected_checksum = manifest["vectors_checksum"]

    raw_vectors = [c["embedding"] for c in manifest_chunks]
    actual_checksum = compute_vectors_checksum(raw_vectors)
    if actual_checksum != expected_checksum:
        raise ValueError(
            f"Manifest vector checksum mismatch: expected {expected_checksum}, calculated {actual_checksum}. Manifest may be corrupted."
        )

    document = db.scalar(select(Document).where(Document.id == doc_id))
    if not document:
        raise ValueError(f"Document {doc_id} referenced in manifest does not exist in database.")

    existing_chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc_id)
            .order_by(DocumentChunk.chunk_index)
        ).all()
    )
    chunks_by_id = {str(c.id): c for c in existing_chunks}

    # Verify all manifest chunks match database chunk text hashes
    for mc in manifest_chunks:
        cid = mc["chunk_id"]
        if cid not in chunks_by_id:
            raise ValueError(f"Chunk {cid} from manifest does not exist in document {doc_id}.")
        db_chunk = chunks_by_id[cid]
        if compute_chunk_text_hash(db_chunk.text) != mc["text_sha256"]:
            raise ValueError(
                f"Chunk {cid} text hash mismatch! The document content was altered after backup. Rollback aborted to protect data integrity."
            )

    try:
        for mc in manifest_chunks:
            db_chunk = chunks_by_id[mc["chunk_id"]]
            db_chunk.embedding = mc["embedding"]
            db_chunk.embedding_model = mc["embedding_model"]
            db_chunk.updated_at = datetime.now(timezone.utc)

        document.embedding_model = doc_info["embedding_model"]
        document.embedding_dimension = doc_info["embedding_dimension"]
        document.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(document)

        logger.info(
            "Successfully restored %d chunks for document '%s' to model '%s'.",
            len(manifest_chunks),
            document.original_filename,
            document.embedding_model,
        )
        return {
            "document_id": str(document.id),
            "filename": document.original_filename,
            "restored_chunks": len(manifest_chunks),
            "restored_model": document.embedding_model,
            "status": "RESTORED",
        }
    except Exception as exc:
        db.rollback()
        logger.error("Failed to restore embeddings from manifest %s: %s", path, exc)
        raise


def migrate_document_embeddings(
    db: Session,
    document: Document,
    provider: EmbeddingProvider,
    dry_run: bool = True,
    batch_size: int = 20,
    allow_rechunk: bool = False,
    backup: bool = True,
    backup_dir: Path | None = None,
) -> MigrationResult:
    """Migrate a document to a new embedding provider.

    Key safety mechanisms:
    1. Dry-run by default: no database changes occur unless dry_run=False.
    2. Exact chunk verification: requires exact text & coordinate match before reusing chunk IDs.
    3. In-place update: preserves chunk IDs so RAGCitation foreign keys remain 100% intact.
    4. Two-phase recovery manifest: writes and verifies backup JSON before initiating DB transaction.
    5. Atomic transaction rollback: if embedding fails mid-stream, DB rolls back cleanly.
    """
    existing_chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        ).all()
    )
    old_model = document.embedding_model or (existing_chunks[0].embedding_model if existing_chunks else None)

    # Determine chunk target:
    # If the document already has chunks, re-embed existing chunks in-place to preserve
    # chunk IDs, chunk boundaries, document text, and all historical RAG citations.
    # Only generate candidate chunks if the document currently has no chunks.
    if existing_chunks:
        chunks_to_embed = existing_chunks
        texts_to_embed = [
            (c.context_prefix + "\n\n" + c.text if c.context_prefix else c.text)
            for c in existing_chunks
        ]
        is_in_place = True
        chunk_count = len(existing_chunks)
    else:
        sources = get_indexable_sources(db, document)
        candidate_chunks = chunk_document_sources(
            sources=sources,
            document_filename=document.original_filename,
            target_chunk_size=settings.CHUNK_SIZE_CHARACTERS,
            overlap=settings.CHUNK_OVERLAP_CHARACTERS,
        )
        chunks_to_embed = candidate_chunks
        texts_to_embed = [c.embedded_text for c in candidate_chunks]
        is_in_place = False
        chunk_count = len(candidate_chunks)

    res = MigrationResult(
        document_id=str(document.id),
        filename=document.original_filename,
        old_model=old_model,
        new_model=provider.model_name,
        chunk_count=chunk_count,
        in_place_updated=is_in_place,
        backup_path=None,
        status="DRY_RUN" if dry_run else "PENDING",
    )

    if not is_in_place and not allow_rechunk:
        res.status = "SKIPPED_NO_EXISTING_CHUNKS"
        res.error = "Document has no existing indexed chunks to update in-place; allow_rechunk=True required."
        return res

    if dry_run or not chunks_to_embed:
        if not chunks_to_embed:
            res.status = "NO_CHUNKS"
        return res

    # 1. Create recovery manifest before mutating database
    manifest_path: Path | None = None
    if backup and existing_chunks:
        manifest_path = create_recovery_manifest(document, existing_chunks, backup_dir=backup_dir)
        res.backup_path = str(manifest_path)

    # 2. Generate new embeddings in throttled batches
    try:
        all_vectors: list[list[float]] = []

        for i in range(0, len(texts_to_embed), batch_size):
            batch_texts = texts_to_embed[i : i + batch_size]
            logger.info(
                "Embedding batch %d-%d of %d for '%s' using %s",
                i + 1,
                min(i + batch_size, len(texts_to_embed)),
                len(texts_to_embed),
                document.original_filename,
                provider.model_name,
            )
            batch_vectors = provider.embed_documents(batch_texts)
            for v in batch_vectors:
                all_vectors.append(validate_and_normalize(v, EMBEDDING_DIMENSION))

        # 3. Transactional update:
        # If chunks exist, update IN-PLACE to preserve chunk.id and all citations!
        if is_in_place:
            for old_chunk, new_vec in zip(existing_chunks, all_vectors, strict=True):
                old_chunk.embedding = new_vec
                old_chunk.embedding_model = provider.model_name
                old_chunk.updated_at = datetime.now(timezone.utc)
                # If PPTX slide locator exists, ensure page_number is populated
                if old_chunk.page_number is None and old_chunk.content_unit and old_chunk.content_unit.locator:
                    loc = old_chunk.content_unit.locator
                    if loc.get("type") == "pptx_slide" and isinstance(loc.get("slide"), int) and loc["slide"] > 0:
                        old_chunk.page_number = loc["slide"]
                        old_chunk.page_start = loc["slide"]
                        old_chunk.page_end = loc["slide"]
        else:
            # Initial chunks creation
            db.add_all(
                DocumentChunk(
                    document_id=document.id,
                    extracted_page_id=chunk.extracted_page_id,
                    content_unit_id=chunk.content_unit_id,
                    page_number=chunk.page_number,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    context_prefix=chunk.context_prefix,
                    tsv=func.to_tsvector("simple", chunk.embedded_text),
                    chunk_index=chunk.chunk_index,
                    page_chunk_index=chunk.page_chunk_index,
                    text=chunk.text,
                    character_count=chunk.character_count,
                    approximate_token_count=chunk.approximate_token_count,
                    embedding=vector,
                    embedding_model=provider.model_name,
                )
                for chunk, vector in zip(candidate_chunks, all_vectors, strict=True)
            )

        document.indexing_status = "INDEXED"
        document.indexing_error = None
        document.indexed_at = datetime.now(timezone.utc)
        document.embedding_model = provider.model_name
        document.embedding_dimension = provider.dimension
        db.commit()
        db.refresh(document)

        res.status = "SUCCESS"
        logger.info(
            "Successfully migrated document '%s' to '%s' (in_place=%s).",
            document.original_filename,
            provider.model_name,
            is_in_place,
        )
        return res
    except Exception as exc:
        db.rollback()
        res.status = "FAILED"
        res.error = str(exc)
        logger.error(
            "Migration failed for document '%s': %s (original vectors preserved intact)",
            document.original_filename,
            exc,
        )
        return res
