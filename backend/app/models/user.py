from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, DateTime, func, text
from datetime import datetime
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    system_role: Mapped[str] = mapped_column(
        String(50), default="USER", server_default="USER", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    external_identities = relationship(
        "ExternalIdentity", back_populates="user", cascade="all, delete-orphan"
    )
    created_workspaces = relationship("Workspace", back_populates="creator")
    workspace_memberships = relationship(
        "WorkspaceMembership", back_populates="user", cascade="all, delete-orphan"
    )
    uploaded_documents = relationship("Document", back_populates="uploader")
    rag_responses = relationship("RAGResponseRecord", back_populates="requester")
    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
