"""Add the v1.4.1 canonical ingestion foundation.

Revision ID: f4a1c2d3e5b6
Revises: e2f4a6b8c0d1
Create Date: 2026-08-26
"""

from datetime import datetime, timezone
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f4a1c2d3e5b6"
down_revision: Union[str, None] = "e2f4a6b8c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("processing_stage", sa.String(length=40), nullable=True)
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("adapter_id", sa.String(length=80), nullable=False),
        sa.Column("adapter_version", sa.String(length=40), nullable=False),
        sa.Column("source_format", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("unit_count", sa.Integer(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name="ck_ingestion_runs_version_positive"),
        sa.CheckConstraint(
            "status IN ('PROCESSING', 'STAGED', 'ACTIVE', 'SUPERSEDED', 'FAILED')",
            name="ck_ingestion_runs_status",
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count >= 0",
            name="ck_ingestion_runs_page_count_nonnegative",
        ),
        sa.CheckConstraint(
            "unit_count IS NULL OR unit_count >= 0",
            name="ck_ingestion_runs_unit_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version", name="uq_ingestion_run_version"),
    )
    op.create_index(
        "ix_ingestion_runs_document_id", "ingestion_runs", ["document_id"], unique=False
    )
    op.create_index(
        "uq_ingestion_runs_active_document",
        "ingestion_runs",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "content_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingestion_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("locator_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("locator", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extraction_method", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "unit_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("ordinal >= 0", name="ck_content_units_ordinal_nonnegative"),
        sa.CheckConstraint(
            "character_count >= 0", name="ck_content_units_character_count_nonnegative"
        ),
        sa.CheckConstraint(
            "locator_version > 0", name="ck_content_units_locator_version_positive"
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_content_units_confidence_range",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"], ["ingestion_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ingestion_run_id", "ordinal", name="uq_content_unit_ordinal"),
    )
    op.create_index(
        "ix_content_units_document_id", "content_units", ["document_id"], unique=False
    )
    op.create_index(
        "ix_content_units_ingestion_run_id",
        "content_units",
        ["ingestion_run_id"],
        unique=False,
    )

    op.add_column(
        "extracted_pages",
        sa.Column("content_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_extracted_pages_content_unit_id",
        "extracted_pages",
        "content_units",
        ["content_unit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_extracted_pages_content_unit_id", "extracted_pages", ["content_unit_id"]
    )

    op.add_column(
        "document_chunks",
        sa.Column("content_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_chunks_content_unit_id",
        "document_chunks",
        "content_units",
        ["content_unit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_chunks_content_unit_id",
        "document_chunks",
        ["content_unit_id"],
        unique=False,
    )

    # Backfill existing PDF pages into one active canonical run per processed document.
    bind = op.get_bind()
    processed_documents = list(
        bind.execute(
            sa.text(
                "SELECT d.id, d.page_count FROM documents d "
                "WHERE d.status = 'PROCESSED' AND EXISTS ("
                "SELECT 1 FROM extracted_pages p WHERE p.document_id = d.id)"
            )
        ).mappings()
    )
    now = datetime.now(timezone.utc)
    for document in processed_documents:
        run_id = uuid.uuid4()
        page_rows = list(
            bind.execute(
                sa.text(
                    "SELECT id, page_number, text, character_count "
                    "FROM extracted_pages WHERE document_id = :document_id "
                    "ORDER BY page_number"
                ),
                {"document_id": document["id"]},
            ).mappings()
        )
        bind.execute(
            sa.text(
                "INSERT INTO ingestion_runs "
                "(id, document_id, version, adapter_id, adapter_version, source_format, "
                "status, page_count, unit_count, started_at, completed_at, created_at) "
                "VALUES (:id, :document_id, 1, 'legacy.pdf', '0.6', 'pdf', "
                "'ACTIVE', :page_count, :unit_count, :now, :now, :now)"
            ),
            {
                "id": run_id,
                "document_id": document["id"],
                "page_count": document["page_count"],
                "unit_count": len(page_rows),
                "now": now,
            },
        )
        for ordinal, page in enumerate(page_rows):
            unit_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    "INSERT INTO content_units "
                    "(id, document_id, ingestion_run_id, ordinal, kind, text, character_count, "
                    "locator_version, locator, extraction_method, unit_metadata, created_at) "
                    "VALUES (:id, :document_id, :run_id, :ordinal, 'PAGE', :text, "
                    ":character_count, 1, CAST(:locator AS jsonb), 'NATIVE_LEGACY', "
                    "'{}'::jsonb, :now)"
                ),
                {
                    "id": unit_id,
                    "document_id": document["id"],
                    "run_id": run_id,
                    "ordinal": ordinal,
                    "text": page["text"],
                    "character_count": page["character_count"],
                    "locator": '{"v":1,"type":"pdf_page","page":%d}'
                    % page["page_number"],
                    "now": now,
                },
            )
            bind.execute(
                sa.text(
                    "UPDATE extracted_pages SET content_unit_id = :unit_id WHERE id = :page_id"
                ),
                {"unit_id": unit_id, "page_id": page["id"]},
            )
    bind.execute(
        sa.text(
            "UPDATE document_chunks c SET content_unit_id = p.content_unit_id "
            "FROM extracted_pages p WHERE c.extracted_page_id = p.id"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_unit_id", table_name="document_chunks")
    op.drop_constraint(
        "fk_document_chunks_content_unit_id", "document_chunks", type_="foreignkey"
    )
    op.drop_column("document_chunks", "content_unit_id")

    op.drop_constraint(
        "uq_extracted_pages_content_unit_id", "extracted_pages", type_="unique"
    )
    op.drop_constraint(
        "fk_extracted_pages_content_unit_id", "extracted_pages", type_="foreignkey"
    )
    op.drop_column("extracted_pages", "content_unit_id")

    op.drop_index("ix_content_units_ingestion_run_id", table_name="content_units")
    op.drop_index("ix_content_units_document_id", table_name="content_units")
    op.drop_table("content_units")
    op.drop_index("uq_ingestion_runs_active_document", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_document_id", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_column("documents", "processing_stage")
