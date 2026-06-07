import uuid
from datetime import date
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.document import Document

class Transaction(BaseModel):
    __tablename__ = "transactions"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    debit_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    credit_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    reference_number: Mapped[str] = mapped_column(String(100), nullable=True)
    merchant_name: Mapped[str] = mapped_column(String(255), index=True, nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="transactions")
