import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_ingestion_run_version"),
        CheckConstraint("version > 0", name="ck_ingestion_runs_version_positive"),
        CheckConstraint(
            "status IN ('PROCESSING', 'STAGED', 'ACTIVE', 'SUPERSEDED', 'FAILED')",
            name="ck_ingestion_runs_status",
        ),
        CheckConstraint(
            "page_count IS NULL OR page_count >= 0",
            name="ck_ingestion_runs_page_count_nonnegative",
        ),
        CheckConstraint(
            "unit_count IS NULL OR unit_count >= 0",
            name="ck_ingestion_runs_unit_count_nonnegative",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('COMPLETE', 'PARTIAL', 'FAILED')",
            name="ck_ingestion_runs_outcome",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_ingestion_runs_duration_nonnegative",
        ),
        Index(
            "uq_ingestion_runs_active_document",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
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
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    adapter_id: Mapped[str] = mapped_column(String(80), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_format: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diagnostics: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    document = relationship("Document", back_populates="ingestion_runs")
    content_units = relationship(
        "ContentUnit",
        back_populates="ingestion_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ContentUnit.ordinal",
    )
