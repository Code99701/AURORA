"""Add page-aware extracted document content.

Revision ID: f93d2ae61c84
Revises: e84c19ad5b72
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f93d2ae61c84"
down_revision: Union[str, None] = "e84c19ad5b72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column(
        "documents", sa.Column("processing_error", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "documents", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "extracted_pages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "character_count >= 0", name="ck_extracted_pages_character_count_nonnegative"
        ),
        sa.CheckConstraint(
            "page_number > 0", name="ck_extracted_pages_page_number_positive"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_extracted_page_number"),
    )
    op.create_index(
        "ix_extracted_pages_document_id", "extracted_pages", ["document_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_extracted_pages_document_id", table_name="extracted_pages")
    op.drop_table("extracted_pages")
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "processing_error")
    op.drop_column("documents", "page_count")
