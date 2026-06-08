"""Update document schema for uploads

Revision ID: 1eefc2901ba4
Revises: 11e3f075c036
Create Date: 2026-06-07 23:30:13.563162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1eefc2901ba4'
down_revision: Union[str, Sequence[str], None] = '11e3f075c036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('file_path', sa.String(length=512), nullable=True))
    op.add_column('documents', sa.Column('status', sa.String(length=50), nullable=True))
    op.add_column('documents', sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE documents SET file_path = filename WHERE file_path IS NULL")
    op.execute("UPDATE documents SET status = processing_status WHERE status IS NULL")
    op.execute("UPDATE documents SET uploaded_at = upload_timestamp WHERE uploaded_at IS NULL")
    op.alter_column('documents', 'file_path', nullable=False)
    op.alter_column('documents', 'status', nullable=False)
    op.alter_column('documents', 'uploaded_at', nullable=False)
    op.drop_index(op.f('ix_documents_processing_status'), table_name='documents')
    op.create_index(op.f('ix_documents_status'), 'documents', ['status'], unique=False)
    op.drop_column('documents', 'upload_timestamp')
    op.drop_column('documents', 'processing_status')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('documents', sa.Column('processing_status', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
    op.add_column('documents', sa.Column('upload_timestamp', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.execute("UPDATE documents SET processing_status = status WHERE processing_status IS NULL")
    op.execute("UPDATE documents SET upload_timestamp = uploaded_at WHERE upload_timestamp IS NULL")
    op.alter_column('documents', 'processing_status', nullable=False)
    op.alter_column('documents', 'upload_timestamp', nullable=False)
    op.drop_index(op.f('ix_documents_status'), table_name='documents')
    op.create_index(op.f('ix_documents_processing_status'), 'documents', ['processing_status'], unique=False)
    op.drop_column('documents', 'uploaded_at')
    op.drop_column('documents', 'status')
    op.drop_column('documents', 'file_path')
