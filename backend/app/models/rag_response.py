import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RAGResponseRecord(Base):
    __tablename__ = "rag_responses"
    __table_args__ = (
        CheckConstraint("top_k > 0", name="ck_rag_responses_top_k_positive"),
        CheckConstraint(
            "citation_count >= 0", name="ck_rag_responses_citation_count_nonnegative"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    answer_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    insufficient_evidence: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    workspace = relationship("Workspace", back_populates="rag_responses")
    requester = relationship("User", back_populates="rag_responses")
    citations = relationship(
        "RAGCitation",
        back_populates="response",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RAGCitation.position",
    )
    conversation_message = relationship(
        "ConversationMessage", back_populates="rag_response", uselist=False
    )
