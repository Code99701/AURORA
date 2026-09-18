import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('UPLOADED', 'PROCESSING', 'PROCESSED', "
            "'PARTIALLY_PROCESSED', 'FAILED')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "indexing_status IN ('NOT_INDEXED', 'INDEXING', 'INDEXED', 'FAILED')",
            name="ck_documents_indexing_status",
        ),
        CheckConstraint("file_size > 0", name="ck_documents_file_size_positive"),
        UniqueConstraint("storage_key", name="uq_documents_storage_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="UPLOADED", server_default="UPLOADED", nullable=False
    )
    page_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    processing_error: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    processing_stage: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    processing_summary: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    indexing_status: Mapped[str] = mapped_column(
        String(30), default="NOT_INDEXED", server_default="NOT_INDEXED", nullable=False
    )
    indexing_error: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding_dimension: Mapped[Optional[int]] = mapped_column(nullable=True)
    indexing_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    workspace = relationship("Workspace", back_populates="documents")
    uploader = relationship("User", back_populates="uploaded_documents")
    extracted_pages = relationship(
        "ExtractedPage",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractedPage.page_number",
    )
    ingestion_runs = relationship(
        "IngestionRun",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="IngestionRun.version",
    )
    content_units = relationship(
        "ContentUnit",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ContentUnit.ordinal",
    )
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.chunk_index",
    )
