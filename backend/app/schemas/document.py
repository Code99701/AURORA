import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    uploaded_by: int
    original_filename: str
    content_type: str
    file_size: int
    checksum: str
    status: Literal[
        "UPLOADED", "PROCESSING", "PROCESSED", "PARTIALLY_PROCESSED", "FAILED"
    ]
    page_count: int | None
    processing_error: str | None
    processing_stage: str | None
    processing_summary: dict
    processed_at: datetime | None
    indexing_status: Literal["NOT_INDEXED", "INDEXING", "INDEXED", "FAILED"]
    indexing_error: str | None
    indexed_at: datetime | None
    embedding_model: str | None
    embedding_dimension: int | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
