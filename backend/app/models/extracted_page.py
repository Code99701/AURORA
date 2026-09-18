import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExtractedPage(Base):
    __tablename__ = "extracted_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_extracted_page_number"),
        CheckConstraint("page_number > 0", name="ck_extracted_pages_page_number_positive"),
        CheckConstraint(
            "character_count >= 0", name="ck_extracted_pages_character_count_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_units.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
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

    document = relationship("Document", back_populates="extracted_pages")
    content_unit = relationship("ContentUnit", back_populates="extracted_page")
    chunks = relationship(
        "DocumentChunk",
        back_populates="extracted_page",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.page_chunk_index",
    )
