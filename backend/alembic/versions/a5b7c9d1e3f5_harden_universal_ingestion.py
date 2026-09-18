"""Harden canonical ingestion outcomes and diagnostics.

Revision ID: a5b7c9d1e3f5
Revises: f4a1c2d3e5b6
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a5b7c9d1e3f5"
down_revision: Union[str, None] = "f4a1c2d3e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('UPLOADED', 'PROCESSING', 'PROCESSED', "
        "'PARTIALLY_PROCESSED', 'FAILED')",
    )
    op.add_column(
        "documents",
        sa.Column(
            "processing_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.add_column(
        "ingestion_runs", sa.Column("failure_stage", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "ingestion_runs", sa.Column("outcome", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "ingestion_runs", sa.Column("duration_ms", sa.Integer(), nullable=True)
    )
    op.add_column(
        "ingestion_runs",
        sa.Column(
            "diagnostics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_ingestion_runs_outcome",
        "ingestion_runs",
        "outcome IS NULL OR outcome IN ('COMPLETE', 'PARTIAL', 'FAILED')",
    )
    op.create_check_constraint(
        "ck_ingestion_runs_duration_nonnegative",
        "ingestion_runs",
        "duration_ms IS NULL OR duration_ms >= 0",
    )
    op.execute(
        "UPDATE ingestion_runs SET outcome = CASE "
        "WHEN status IN ('ACTIVE', 'SUPERSEDED') THEN 'COMPLETE' "
        "WHEN status = 'FAILED' THEN 'FAILED' ELSE NULL END"
    )

    op.add_column(
        "content_units",
        sa.Column("parent_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "content_units",
        sa.Column(
            "content_type",
            sa.String(length=100),
            server_default="text/plain",
            nullable=False,
        ),
    )
    op.add_column(
        "content_units",
        sa.Column(
            "status", sa.String(length=20), server_default="USABLE", nullable=False
        ),
    )
    op.add_column(
        "content_units", sa.Column("issue_code", sa.String(length=64), nullable=True)
    )
    op.create_foreign_key(
        "fk_content_units_parent_unit_id",
        "content_units",
        "content_units",
        ["parent_unit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_content_units_parent_unit_id",
        "content_units",
        ["parent_unit_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_content_units_status",
        "content_units",
        "status IN ('USABLE', 'SKIPPED', 'FAILED')",
    )
    op.create_check_constraint(
        "ck_content_units_parent_not_self",
        "content_units",
        "parent_unit_id IS NULL OR parent_unit_id <> id",
    )
    op.execute(
        "UPDATE content_units SET status = CASE "
        "WHEN character_count > 0 THEN 'USABLE' ELSE 'SKIPPED' END, "
        "issue_code = CASE WHEN character_count = 0 THEN 'BLANK_PAGE' ELSE NULL END"
    )
    op.execute(
        "UPDATE ingestion_runs r SET diagnostics = jsonb_build_object("
        "'page_count', r.page_count, 'unit_count', r.unit_count, "
        "'usable_unit_count', (SELECT count(*) FROM content_units u "
        "WHERE u.ingestion_run_id = r.id AND u.status = 'USABLE'), "
        "'skipped_unit_count', (SELECT count(*) FROM content_units u "
        "WHERE u.ingestion_run_id = r.id AND u.status = 'SKIPPED'), "
        "'failed_unit_count', (SELECT count(*) FROM content_units u "
        "WHERE u.ingestion_run_id = r.id AND u.status = 'FAILED'))"
    )
    op.execute(
        "UPDATE documents d SET processing_summary = r.diagnostics "
        "FROM ingestion_runs r WHERE r.document_id = d.id AND r.status = 'ACTIVE'"
    )

    op.drop_constraint("uq_page_chunk_index", "document_chunks", type_="unique")
    op.drop_constraint(
        "ck_document_chunks_page_positive", "document_chunks", type_="check"
    )
    op.alter_column("document_chunks", "extracted_page_id", nullable=True)
    op.alter_column("document_chunks", "page_number", nullable=True)
    op.create_unique_constraint(
        "uq_content_unit_chunk_index",
        "document_chunks",
        ["content_unit_id", "page_chunk_index"],
    )
    op.create_check_constraint(
        "ck_document_chunks_page_positive",
        "document_chunks",
        "page_number IS NULL OR page_number > 0",
    )


def downgrade() -> None:
    # v1.4.1 only created page-backed chunks, so canonical chunks without a
    # legacy page must be removed before restoring its non-null page contract.
    op.execute("DELETE FROM document_chunks WHERE extracted_page_id IS NULL")
    op.drop_constraint(
        "ck_document_chunks_page_positive", "document_chunks", type_="check"
    )
    op.drop_constraint(
        "uq_content_unit_chunk_index", "document_chunks", type_="unique"
    )
    op.alter_column("document_chunks", "page_number", nullable=False)
    op.alter_column("document_chunks", "extracted_page_id", nullable=False)
    op.create_unique_constraint(
        "uq_page_chunk_index",
        "document_chunks",
        ["extracted_page_id", "page_chunk_index"],
    )
    op.create_check_constraint(
        "ck_document_chunks_page_positive",
        "document_chunks",
        "page_number > 0",
    )

    op.drop_constraint(
        "ck_content_units_parent_not_self", "content_units", type_="check"
    )
    op.drop_constraint("ck_content_units_status", "content_units", type_="check")
    op.drop_index("ix_content_units_parent_unit_id", table_name="content_units")
    op.drop_constraint(
        "fk_content_units_parent_unit_id", "content_units", type_="foreignkey"
    )
    op.drop_column("content_units", "issue_code")
    op.drop_column("content_units", "status")
    op.drop_column("content_units", "content_type")
    op.drop_column("content_units", "parent_unit_id")

    op.drop_constraint(
        "ck_ingestion_runs_duration_nonnegative", "ingestion_runs", type_="check"
    )
    op.drop_constraint("ck_ingestion_runs_outcome", "ingestion_runs", type_="check")
    op.drop_column("ingestion_runs", "diagnostics")
    op.drop_column("ingestion_runs", "duration_ms")
    op.drop_column("ingestion_runs", "outcome")
    op.drop_column("ingestion_runs", "failure_stage")

    op.drop_column("documents", "processing_summary")
    op.execute(
        "UPDATE documents SET status = 'PROCESSED' "
        "WHERE status = 'PARTIALLY_PROCESSED'"
    )
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('UPLOADED', 'PROCESSING', 'PROCESSED', 'FAILED')",
    )
