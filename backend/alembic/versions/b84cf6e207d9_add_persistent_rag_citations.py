"""Add persistent RAG responses and citations.

Revision ID: b84cf6e207d9
Revises: a72b19c64e31
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b84cf6e207d9"
down_revision: Union[str, None] = "a72b19c64e31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rag_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("answer_language", sa.String(length=50), nullable=True),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("citation_count", sa.Integer(), nullable=False),
        sa.Column("insufficient_evidence", sa.Boolean(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("top_k > 0", name="ck_rag_responses_top_k_positive"),
        sa.CheckConstraint(
            "citation_count >= 0", name="ck_rag_responses_citation_count_nonnegative"
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_responses_workspace_id", "rag_responses", ["workspace_id"])
    op.create_index("ix_rag_responses_requested_by", "rag_responses", ["requested_by"])

    op.create_table(
        "rag_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("position > 0", name="ck_rag_citations_position_positive"),
        sa.CheckConstraint(
            "similarity >= -1 AND similarity <= 1",
            name="ck_rag_citations_similarity_range",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["response_id"], ["rag_responses.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("response_id", "chunk_id", name="uq_rag_citation_chunk"),
        sa.UniqueConstraint("response_id", "position", name="uq_rag_citation_position"),
    )
    op.create_index("ix_rag_citations_response_id", "rag_citations", ["response_id"])
    op.create_index("ix_rag_citations_chunk_id", "rag_citations", ["chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_citations_chunk_id", table_name="rag_citations")
    op.drop_index("ix_rag_citations_response_id", table_name="rag_citations")
    op.drop_table("rag_citations")
    op.drop_index("ix_rag_responses_requested_by", table_name="rag_responses")
    op.drop_index("ix_rag_responses_workspace_id", table_name="rag_responses")
    op.drop_table("rag_responses")
