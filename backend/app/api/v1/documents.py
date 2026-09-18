import uuid
from collections.abc import Iterator
from typing import BinaryIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_workspace_member, require_workspace_owner
from app.core.config import settings
from app.db.session import get_db
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services import document as document_service
from app.services import processing as processing_service
from app.storage.base import FileStorage, StorageError, StorageNotFoundError
from app.storage.deps import get_file_storage
from app.embeddings.base import EmbeddingProvider
from app.embeddings.deps import get_embedding_provider
from app.services import indexing as indexing_service
from app.ocr.base import OCRProvider
from app.ocr.deps import get_ocr_provider


router = APIRouter()


def _document_or_404(
    db: Session, workspace: Workspace, document_id: uuid.UUID
) -> Document:
    document = document_service.get_document(db, workspace, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document


def _stream_file(handle: BinaryIO) -> Iterator[bytes]:
    try:
        while chunk := handle.read(1024 * 1024):
            yield chunk
    finally:
        handle.close()


@router.post(
    "/{workspace_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> Document:
    try:
        return document_service.create_document(
            db,
            storage,
            workspace,
            current_user,
            file,
            settings.DOCUMENT_MAX_SIZE_BYTES,
        )
    except document_service.DocumentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except document_service.DocumentStorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is unavailable",
        )
    except document_service.DocumentPersistenceError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register document",
        )
    finally:
        file.file.close()


@router.get("/{workspace_id}/documents", response_model=DocumentListResponse)
def list_documents(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    items = document_service.list_documents(db, workspace)
    return DocumentListResponse(items=items, total=len(items))


@router.get("/{workspace_id}/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> Document:
    return _document_or_404(db, workspace, document_id)


@router.get("/{workspace_id}/documents/{document_id}/download")
def download_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> StreamingResponse:
    document = _document_or_404(db, workspace, document_id)
    try:
        handle = storage.open(document.storage_key)
    except StorageNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored document not found",
        )
    except StorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is unavailable",
        )

    encoded_filename = quote(document.original_filename, safe="")
    return StreamingResponse(
        _stream_file(handle),
        media_type=document.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )


@router.get("/{workspace_id}/documents/{document_id}/preview")
def preview_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> StreamingResponse:
    """Stream an authorized document inline for the research inspector."""
    document = _document_or_404(db, workspace, document_id)
    if document.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Document preview is unavailable for this file type",
        )
    try:
        handle = storage.open(document.storage_key)
    except StorageNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored document not found",
        )
    except StorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is unavailable",
        )

    encoded_filename = quote(document.original_filename, safe="")
    return StreamingResponse(
        _stream_file(handle),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/{workspace_id}/documents/{document_id}/process",
    response_model=DocumentResponse,
)
def process_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
    ocr_provider: OCRProvider = Depends(get_ocr_provider),
) -> Document:
    document = _document_or_404(db, workspace, document_id)
    try:
        return processing_service.process_document(db, storage, document, ocr_provider)
    except processing_service.DocumentProcessingError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.public_message},
        )


@router.post(
    "/{workspace_id}/documents/{document_id}/index",
    response_model=DocumentResponse,
)
def index_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    db: Session = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> Document:
    document = _document_or_404(db, workspace, document_id)
    try:
        return indexing_service.index_document(db, document, provider)
    except indexing_service.DocumentIndexingError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.public_message},
        )


@router.delete(
    "/{workspace_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_owner),
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> Response:
    document = _document_or_404(db, workspace, document_id)
    try:
        document_service.delete_document(db, storage, document)
    except document_service.DocumentStorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is unavailable",
        )
    except document_service.DocumentPersistenceError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete document",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
