import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime, Uuid

class Base(DeclarativeBase):
    """
    SQLAlchemy Declarative Base for ORM models.
    Provides shared attributes and metadata mapping for all models.
    """
    pass

class BaseModel(Base):
    """
    Abstract Base Model Mixin providing UUID primary keys and standard audit timestamps.
    Inherited by all relational entities for consistency.
    """
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4, 
        index=True
    )
    
    # Store timestamps in UTC format for global consistency
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
