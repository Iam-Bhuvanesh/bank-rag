import uuid
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.transaction import Transaction

class Document(BaseModel):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=True) # size in bytes
    
    # Updated columns for Document Management
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="UPLOADED", index=True, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    pdf_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    extracted_text_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ocr_status: Mapped[str] = mapped_column(
        String(50), default="NOT_REQUIRED", index=True, nullable=False
    )
    ocr_text_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ocr_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="documents")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="document", cascade="all, delete-orphan")
