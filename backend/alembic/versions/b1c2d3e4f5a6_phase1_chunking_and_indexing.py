"""Phase 1: Chunking and Indexing extensions.

Revision ID: b1c2d3e4f5a6
Revises: a5b7c9d1e3f5
Create Date: 2026-10-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a5b7c9d1e3f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update check constraint on documents.indexing_status to allow PARTIAL
    op.drop_constraint("ck_documents_indexing_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_indexing_status",
        "documents",
        "indexing_status IN ('NOT_INDEXED', 'INDEXING', 'INDEXED', 'PARTIAL', 'FAILED')",
    )

    # 2. Add columns to documents: content_hash, summary, outline
    op.add_column("documents", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "outline",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_documents_workspace_content_hash",
        "documents",
        ["workspace_id", "content_hash"],
    )

    # 3. Add columns to document_chunks: page_start, page_end, parent_chunk_id, context_prefix, tsv
    op.add_column("document_chunks", sa.Column("page_start", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column(
            "parent_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("document_chunks", sa.Column("context_prefix", sa.Text(), nullable=True))
    op.add_column("document_chunks", sa.Column("tsv", postgresql.TSVECTOR(), nullable=True))

    # 4. Indexes on document_chunks
    op.create_index(
        "ix_document_chunks_doc_pages",
        "document_chunks",
        ["document_id", "page_start", "page_end"],
    )
    op.create_index(
        "ix_document_chunks_tsv",
        "document_chunks",
        ["tsv"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_tsv", table_name="document_chunks")
    op.drop_index("ix_document_chunks_doc_pages", table_name="document_chunks")
    op.drop_column("document_chunks", "tsv")
    op.drop_column("document_chunks", "context_prefix")
    op.drop_column("document_chunks", "parent_chunk_id")
    op.drop_column("document_chunks", "page_end")
    op.drop_column("document_chunks", "page_start")

    op.drop_index("ix_documents_workspace_content_hash", table_name="documents")
    op.drop_column("documents", "outline")
    op.drop_column("documents", "summary")
    op.drop_column("documents", "content_hash")

    op.drop_constraint("ck_documents_indexing_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_indexing_status",
        "documents",
        "indexing_status IN ('NOT_INDEXED', 'INDEXING', 'INDEXED', 'FAILED')",
    )
