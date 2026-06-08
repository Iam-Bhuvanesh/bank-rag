import logging
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.user import User
from app.ocr.services.ocr_service import OCR_STATUS_PENDING
from app.repositories.document_repository import document_repo
from app.services.storage_service import storage_service

OCR_IMAGE_FILE_TYPES = {"png", "jpg", "jpeg"}

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Coordinates document storage and metadata persistence.
    """

    async def upload_document(
        self, db: AsyncSession, *, file: UploadFile, user: User
    ) -> Document:
        stored_filename, file_path, file_size = await storage_service.save_file(
            file=file,
            user_id=user.id,
        )

        file_type = stored_filename.rsplit(".", 1)[-1].lower()
        ocr_status = OCR_STATUS_PENDING if file_type in OCR_IMAGE_FILE_TYPES else "NOT_REQUIRED"

        try:
            document = await document_repo.create_document(
                db=db,
                user_id=user.id,
                filename=stored_filename,
                original_filename=file.filename or stored_filename,
                file_type=file_type,
                file_size=file_size,
                file_path=file_path,
                status="UPLOADED",
                ocr_status=ocr_status,
            )
        except Exception:
            storage_service.delete_file(file_path)
            logger.exception("Document metadata creation failed; removed stored file.")
            raise

        logger.info("Uploaded document %s for user %s", document.id, user.id)
        return document

    async def get_document(
        self, db: AsyncSession, *, document_id: UUID, user: User
    ) -> Document:
        document = await document_repo.get_document_by_id(db, document_id)
        if not document or document.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )
        return document

    async def list_documents(
        self, db: AsyncSession, *, user: User
    ) -> list[Document]:
        return await document_repo.get_documents_by_user(db, user_id=user.id)

    async def delete_document(
        self, db: AsyncSession, *, document_id: UUID, user: User
    ) -> None:
        document = await self.get_document(db, document_id=document_id, user=user)
        file_path = document.file_path
        await document_repo.delete_document(db, document)
        storage_service.delete_file(file_path)
        logger.info("Deleted document %s for user %s", document_id, user.id)


document_service = DocumentService()
