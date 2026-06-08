from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document
from app.repositories.base import BaseRepository

class DocumentRepository(BaseRepository[Document, Any, Any]): # type: ignore
    """
    Document specific repository for handling statement file metadata operations.
    """
    def __init__(self):
        super().__init__(Document)

    async def create_document(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        filename: str,
        original_filename: str,
        file_type: str,
        file_size: int,
        file_path: str,
        status: str = "UPLOADED",
        ocr_status: str = "NOT_REQUIRED",
    ) -> Document:
        """
        Creates document metadata after the file has been stored successfully.
        """
        document = Document(
            user_id=user_id,
            filename=filename,
            original_filename=original_filename,
            file_type=file_type,
            file_size=file_size,
            file_path=file_path,
            status=status,
            ocr_status=ocr_status,
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)
        return document

    async def get_document_by_id(
        self, db: AsyncSession, document_id: UUID
    ) -> Optional[Document]:
        """
        Retrieves one document by primary key.
        """
        return await self.get_by_id(db, document_id)

    async def get_documents_by_user(
        self, db: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Document]:
        """
        Retrieves all documents uploaded by a specific user.
        """
        query = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.uploaded_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self, db: AsyncSession, doc_id: UUID, status: str
    ) -> Optional[Document]:
        """
        Updates the processing status of a document (e.g. UPLOADED -> PROCESSING -> PROCESSED).
        """
        query = (
            update(self.model)
            .where(self.model.id == doc_id)
            .values(status=status)
        )
        await db.execute(query)
        await db.flush()
        # Retrieve the updated object
        return await self.get_by_id(db, doc_id)

    async def update_processing_metadata(
        self,
        db: AsyncSession,
        *,
        document: Document,
        status: str,
        pdf_type: Optional[str] = None,
        extracted_text_path: Optional[str] = None,
        processed_at: Optional[datetime] = None,
        ocr_status: Optional[str] = None,
    ) -> Document:
        """
        Updates PDF processing fields after text and table extraction.
        """
        document.status = status
        if pdf_type is not None:
            document.pdf_type = pdf_type
        if extracted_text_path is not None:
            document.extracted_text_path = extracted_text_path
        if processed_at is not None:
            document.processed_at = processed_at
        if ocr_status is not None:
            document.ocr_status = ocr_status

        db.add(document)
        await db.flush()
        await db.refresh(document)
        return document

    async def update_ocr_metadata(
        self,
        db: AsyncSession,
        *,
        document: Document,
        ocr_status: str,
        ocr_text_path: Optional[str] = None,
        ocr_processed_at: Optional[datetime] = None,
    ) -> Document:
        """
        Updates OCR processing fields after text extraction.
        """
        document.ocr_status = ocr_status
        if ocr_text_path is not None:
            document.ocr_text_path = ocr_text_path
        if ocr_processed_at is not None:
            document.ocr_processed_at = ocr_processed_at

        db.add(document)
        await db.flush()
        await db.refresh(document)
        return document

    async def delete_document(
        self, db: AsyncSession, document: Document
    ) -> None:
        """
        Deletes document metadata. Physical file cleanup is handled by the service layer.
        """
        await db.delete(document)
        await db.flush()

document_repo = DocumentRepository()
