import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContentUnit(Base):
    __tablename__ = "content_units"
    __table_args__ = (
        UniqueConstraint("ingestion_run_id", "ordinal", name="uq_content_unit_ordinal"),
        CheckConstraint("ordinal >= 0", name="ck_content_units_ordinal_nonnegative"),
        CheckConstraint(
            "character_count >= 0", name="ck_content_units_character_count_nonnegative"
        ),
        CheckConstraint("locator_version > 0", name="ck_content_units_locator_version_positive"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_content_units_confidence_range",
        ),
        CheckConstraint(
            "status IN ('USABLE', 'SKIPPED', 'FAILED')",
            name="ck_content_units_status",
        ),
        CheckConstraint(
            "parent_unit_id IS NULL OR parent_unit_id <> id",
            name="ck_content_units_parent_not_self",
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
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    locator_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    locator: Mapped[dict] = mapped_column(JSONB, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(100), default="text/plain", server_default="text/plain", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="USABLE", server_default="USABLE", nullable=False
    )
    issue_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_metadata: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    document = relationship("Document", back_populates="content_units")
    ingestion_run = relationship("IngestionRun", back_populates="content_units")
    extracted_page = relationship(
        "ExtractedPage", back_populates="content_unit", uselist=False
    )
    chunks = relationship("DocumentChunk", back_populates="content_unit")
    parent = relationship(
        "ContentUnit",
        remote_side=[id],
        back_populates="children",
        foreign_keys=[parent_unit_id],
    )
    children = relationship(
        "ContentUnit",
        back_populates="parent",
        foreign_keys=[parent_unit_id],
    )
