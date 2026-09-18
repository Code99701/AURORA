from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import func
from datetime import datetime
from app.db.base import Base

class VerificationModel(Base):
    """
    A minimal verification table to prove that SQLAlchemy, Alembic, 
    and PostgreSQL migrations are working end-to-end.
    """
    __tablename__ = "db_verification"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now(), nullable=False
    )
