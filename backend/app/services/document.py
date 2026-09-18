import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.storage.base import FileStorage, StorageError
from app.core.config import settings
from app.ingestion.detection import format_spec_for, validate_signature


logger = logging.getLogger(__name__)
READ_CHUNK_SIZE = 1024 * 1024


class DocumentValidationError(Exception):
    pass


class DocumentStorageError(Exception):
    pass


class DocumentPersistenceError(Exception):
    pass


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    content_type: str
    file_size: int
    checksum: str


def normalize_filename(filename: str | None) -> str:
    """Return a display-only filename with path and control characters removed."""
    if not filename or "\x00" in filename:
        raise DocumentValidationError("A valid filename is required")
    basename = PurePosixPath(filename.replace("\\", "/")).name.strip()
    basename = re.sub(r"[\x00-\x1f\x7f]", "", basename)
    if not basename or basename in {".", ".."}:
        raise DocumentValidationError("A valid filename is required")
    if len(basename) > 255:
        raise DocumentValidationError("Filename is too long")
    return basename


def validate_upload(upload: UploadFile, maximum_size: int) -> ValidatedUpload:
    filename = normalize_filename(upload.filename)
    declared_type = (upload.content_type or "").casefold()
    spec = format_spec_for(filename, declared_type)
    if spec is None:
        raise DocumentValidationError(
            "Unsupported document type or filename/MIME mismatch. Supported formats: "
            "PDF, TXT, Markdown, CSV, TSV, DOCX, XLSX, and PPTX"
        )

    checksum = hashlib.sha256()
    total_size = 0
    upload.file.seek(0)
    while chunk := upload.file.read(READ_CHUNK_SIZE):
        total_size += len(chunk)
        if total_size > maximum_size:
            upload.file.seek(0)
            raise DocumentValidationError(
                f"Document exceeds the {maximum_size}-byte upload limit"
            )
        checksum.update(chunk)
    upload.file.seek(0)

    if total_size == 0:
        raise DocumentValidationError("Empty files cannot be uploaded")
    try:
        validate_signature(
            upload.file,
            spec,
            maximum_archive_entries=settings.OOXML_MAX_ARCHIVE_ENTRIES,
            maximum_archive_uncompressed_bytes=settings.OOXML_MAX_UNCOMPRESSED_BYTES,
        )
    except ValueError as exc:
        raise DocumentValidationError(str(exc)) from exc
    finally:
        upload.file.seek(0)

    return ValidatedUpload(
        filename=filename,
        content_type=spec.canonical_media_type,
        file_size=total_size,
        checksum=checksum.hexdigest(),
    )


def build_storage_key(workspace_id: uuid.UUID, document_id: uuid.UUID) -> str:
    return f"workspaces/{workspace_id}/documents/{document_id}/original"


def create_document(
    db: Session,
    storage: FileStorage,
    workspace: Workspace,
    uploader: User,
    upload: UploadFile,
    maximum_size: int,
) -> Document:
    metadata = validate_upload(upload, maximum_size)
    document_id = uuid.uuid4()
    storage_key = build_storage_key(workspace.id, document_id)

    try:
        storage.save(storage_key, upload.file)
    except StorageError as exc:
        raise DocumentStorageError("Unable to store document") from exc

    document = Document(
        id=document_id,
        workspace_id=workspace.id,
        uploaded_by=uploader.id,
        original_filename=metadata.filename,
        storage_provider=storage.provider_name,
        storage_key=storage_key,
        content_type=metadata.content_type,
        file_size=metadata.file_size,
        checksum=metadata.checksum,
        status="UPLOADED",
    )
    try:
        db.add(document)
        db.commit()
        db.refresh(document)
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            storage.delete(storage_key)
        except StorageError:
            logger.error(
                "Document metadata failed and compensating storage cleanup also failed"
            )
        raise DocumentPersistenceError("Unable to register document") from exc
    return document


def list_documents(db: Session, workspace: Workspace) -> list[Document]:
    statement = (
        select(Document)
        .where(Document.workspace_id == workspace.id)
        .order_by(Document.created_at, Document.id)
    )
    return list(db.scalars(statement).all())


def get_document(
    db: Session, workspace: Workspace, document_id: uuid.UUID
) -> Document | None:
    return db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace.id,
        )
    )


def delete_document(db: Session, storage: FileStorage, document: Document) -> None:
    try:
        storage.delete(document.storage_key)
    except StorageError as exc:
        raise DocumentStorageError("Unable to delete stored document") from exc
    try:
        db.delete(document)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise DocumentPersistenceError("Unable to delete document metadata") from exc
