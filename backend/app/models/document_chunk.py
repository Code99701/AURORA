import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


EMBEDDING_DIMENSION = 768


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        UniqueConstraint(
            "content_unit_id", "page_chunk_index", name="uq_content_unit_chunk_index"
        ),
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index_nonnegative"),
        CheckConstraint(
            "page_chunk_index >= 0", name="ck_document_chunks_page_index_nonnegative"
        ),
        CheckConstraint(
            "page_number IS NULL OR page_number > 0",
            name="ck_document_chunks_page_positive",
        ),
        CheckConstraint(
            "character_count > 0", name="ck_document_chunks_character_count_positive"
        ),
        CheckConstraint(
            "approximate_token_count > 0",
            name="ck_document_chunks_token_count_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("extracted_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    content_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    approximate_token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
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

    document = relationship("Document", back_populates="chunks")
    extracted_page = relationship("ExtractedPage", back_populates="chunks")
    content_unit = relationship("ContentUnit", back_populates="chunks")
    citations = relationship(
        "RAGCitation",
        back_populates="chunk",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
