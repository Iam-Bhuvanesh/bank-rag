"""Add PDF processing fields to documents

Revision ID: 8b0f5c4e91a2
Revises: 1eefc2901ba4
Create Date: 2026-06-07 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8b0f5c4e91a2"
down_revision: Union[str, Sequence[str], None] = "1eefc2901ba4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("documents", sa.Column("pdf_type", sa.String(length=50), nullable=True))
    op.add_column("documents", sa.Column("extracted_text_path", sa.String(length=512), nullable=True))
    op.add_column("documents", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "extracted_text_path")
    op.drop_column("documents", "pdf_type")
