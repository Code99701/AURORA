import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RAGCitation(Base):
    __tablename__ = "rag_citations"
    __table_args__ = (
        UniqueConstraint("response_id", "position", name="uq_rag_citation_position"),
        UniqueConstraint("response_id", "chunk_id", name="uq_rag_citation_chunk"),
        CheckConstraint("position > 0", name="ck_rag_citations_position_positive"),
        CheckConstraint(
            "similarity >= -1 AND similarity <= 1",
            name="ck_rag_citations_similarity_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    response = relationship("RAGResponseRecord", back_populates="citations")
    chunk = relationship("DocumentChunk", back_populates="citations")
