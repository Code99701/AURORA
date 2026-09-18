"""Add pgvector-backed RAG data pipeline.

Revision ID: a72b19c64e31
Revises: f93d2ae61c84
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a72b19c64e31"
down_revision: Union[str, None] = "f93d2ae61c84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "documents",
        sa.Column(
            "indexing_status",
            sa.String(length=30),
            server_default="NOT_INDEXED",
            nullable=False,
        ),
    )
    op.add_column("documents", sa.Column("indexing_error", sa.String(length=64)))
    op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True)))
    op.add_column("documents", sa.Column("embedding_model", sa.String(length=100)))
    op.add_column("documents", sa.Column("embedding_dimension", sa.Integer()))
    op.add_column("documents", sa.Column("indexing_fingerprint", sa.String(length=64)))
    op.create_check_constraint(
        "ck_documents_indexing_status",
        "documents",
        "indexing_status IN ('NOT_INDEXED', 'INDEXING', 'INDEXED', 'FAILED')",
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extracted_page_id", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("approximate_token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index_nonnegative"),
        sa.CheckConstraint(
            "page_chunk_index >= 0", name="ck_document_chunks_page_index_nonnegative"
        ),
        sa.CheckConstraint("page_number > 0", name="ck_document_chunks_page_positive"),
        sa.CheckConstraint(
            "character_count > 0", name="ck_document_chunks_character_count_positive"
        ),
        sa.CheckConstraint(
            "approximate_token_count > 0", name="ck_document_chunks_token_count_positive"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["extracted_page_id"], ["extracted_pages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        sa.UniqueConstraint(
            "extracted_page_id", "page_chunk_index", name="uq_page_chunk_index"
        ),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index(
        "ix_document_chunks_extracted_page_id", "document_chunks", ["extracted_page_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_extracted_page_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_constraint("ck_documents_indexing_status", "documents", type_="check")
    op.drop_column("documents", "indexing_fingerprint")
    op.drop_column("documents", "embedding_dimension")
    op.drop_column("documents", "embedding_model")
    op.drop_column("documents", "indexed_at")
    op.drop_column("documents", "indexing_error")
    op.drop_column("documents", "indexing_status")
    # The vector extension is intentionally retained: another schema may use it.
