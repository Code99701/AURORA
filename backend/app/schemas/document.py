import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    uploaded_by: int
    original_filename: str
    content_type: str
    file_size: int
    checksum: str
    content_hash: str | None = None
    summary: str | None = None
    outline: dict | list | None = None
    status: Literal[
        "UPLOADED", "PROCESSING", "PROCESSED", "PARTIALLY_PROCESSED", "FAILED"
    ]
    page_count: int | None
    processing_error: str | None
    processing_stage: str | None
    processing_summary: dict
    processed_at: datetime | None
    indexing_status: Literal["NOT_INDEXED", "INDEXING", "INDEXED", "PARTIAL", "FAILED"]
    indexing_error: str | None
    indexed_at: datetime | None
    embedding_model: str | None
    embedding_dimension: int | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def can_retry(self) -> bool:
        return (
            self.status in ("FAILED", "PARTIALLY_PROCESSED")
            or self.indexing_status in ("FAILED", "PARTIAL")
        )

    @computed_field
    @property
    def retry_action(self) -> str | None:
        if self.can_retry:
            return f"/api/v1/workspaces/{self.workspace_id}/documents/{self.id}/retry"
        return None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
