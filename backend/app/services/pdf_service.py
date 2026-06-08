import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.user import User
from app.repositories.document_repository import document_repo
from app.ocr.services.ocr_service import OCR_STATUS_NOT_REQUIRED, OCR_STATUS_PENDING
from app.utils.pdf_utils import (
    SCANNED_PDF,
    detect_pdf_type,
    extract_tables,
    extract_text,
    load_processed_tables,
    load_processed_text,
    save_processed_text,
)

logger = logging.getLogger(__name__)


class PDFService:
    """
    Processes uploaded PDF statements into extracted text and table artifacts.
    """

    async def _get_owned_document(
        self, db: AsyncSession, *, document_id: UUID, user: User
    ) -> Document:
        document = await document_repo.get_document_by_id(db, document_id)
        if not document or document.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )
        return document

    def _validate_processable_pdf(self, document: Document) -> None:
        if (document.file_type or "").lower() != "pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF documents can be processed by this endpoint.",
            )
        if not Path(document.file_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source PDF file was not found.",
            )

    async def process_document(
        self, db: AsyncSession, *, document_id: UUID, user: User
    ) -> tuple[Document, str, list[dict[str, str]]]:
        document = await self._get_owned_document(db, document_id=document_id, user=user)
        self._validate_processable_pdf(document)

        await document_repo.update_processing_metadata(
            db,
            document=document,
            status="PROCESSING",
        )

        try:
            pdf_type = detect_pdf_type(document.file_path)
            extracted_text = "" if pdf_type == SCANNED_PDF else extract_text(document.file_path)
            extracted_tables = [] if pdf_type == SCANNED_PDF else extract_tables(document.file_path)
            text_path = save_processed_text(
                document_id=str(document.id),
                text=extracted_text,
                tables=extracted_tables,
            )

            ocr_status = OCR_STATUS_PENDING if pdf_type == SCANNED_PDF else OCR_STATUS_NOT_REQUIRED
            document = await document_repo.update_processing_metadata(
                db,
                document=document,
                status="PROCESSED",
                pdf_type=pdf_type,
                extracted_text_path=text_path,
                processed_at=datetime.now(timezone.utc),
                ocr_status=ocr_status,
            )
            logger.info("Processed PDF document %s for user %s", document.id, user.id)
            return document, extracted_text, extracted_tables
        except HTTPException:
            await document_repo.update_processing_metadata(
                db,
                document=document,
                status="FAILED",
                processed_at=datetime.now(timezone.utc),
            )
            await db.commit()
            raise
        except Exception as exc:
            await document_repo.update_processing_metadata(
                db,
                document=document,
                status="FAILED",
                processed_at=datetime.now(timezone.utc),
            )
            await db.commit()
            logger.exception("PDF processing failed for document %s", document.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PDF processing failed.",
            ) from exc

    async def get_processed_content(
        self, db: AsyncSession, *, document_id: UUID, user: User
    ) -> tuple[Document, str, list[dict[str, str]]]:
        document = await self._get_owned_document(db, document_id=document_id, user=user)
        if not document.extracted_text_path or document.status != "PROCESSED":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processed content not found.",
            )

        text = load_processed_text(document.extracted_text_path)
        tables = load_processed_tables(document.extracted_text_path)
        return document, text, tables


pdf_service = PDFService()
