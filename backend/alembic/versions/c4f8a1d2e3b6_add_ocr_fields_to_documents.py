"""Add OCR fields to documents

Revision ID: c4f8a1d2e3b6
Revises: 8b0f5c4e91a2
Create Date: 2026-06-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4f8a1d2e3b6"
down_revision: Union[str, Sequence[str], None] = "8b0f5c4e91a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "documents",
        sa.Column("ocr_status", sa.String(length=50), nullable=False, server_default="NOT_REQUIRED"),
    )
    op.add_column("documents", sa.Column("ocr_text_path", sa.String(length=512), nullable=True))
    op.add_column("documents", sa.Column("ocr_processed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_documents_ocr_status"), "documents", ["ocr_status"], unique=False)
    op.alter_column("documents", "ocr_status", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_documents_ocr_status"), table_name="documents")
    op.drop_column("documents", "ocr_processed_at")
    op.drop_column("documents", "ocr_text_path")
    op.drop_column("documents", "ocr_status")
