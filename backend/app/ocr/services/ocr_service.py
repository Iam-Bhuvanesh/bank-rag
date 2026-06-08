import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.user import User
from app.ocr.utils.image_utils import load_image, preprocess_image, save_processed_image
from app.ocr.utils.ocr_utils import extract_text_with_fallback, load_ocr_text, save_ocr_text
from app.repositories.document_repository import document_repo
from app.utils.pdf_utils import SCANNED_PDF, TEXT_PDF

logger = logging.getLogger(__name__)

OCR_STATUS_NOT_REQUIRED = "NOT_REQUIRED"
OCR_STATUS_PENDING = "PENDING"
OCR_STATUS_PROCESSING = "PROCESSING"
OCR_STATUS_COMPLETED = "COMPLETED"
OCR_STATUS_FAILED = "FAILED"

OCR_IMAGE_FILE_TYPES = {"png", "jpg", "jpeg"}


class OCRService:
    """
    Orchestrates OCR processing for scanned PDFs and image statements.
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

    def _validate_file_size(self, document: Document) -> None:
        if document.file_size and document.file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File exceeds the maximum allowed size for OCR processing.",
            )

    def _validate_ocr_eligible(self, document: Document) -> None:
        file_type = (document.file_type or "").lower()
        source_path = Path(document.file_path)

        if not source_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source file was not found.",
            )

        self._validate_file_size(document)

        if file_type in OCR_IMAGE_FILE_TYPES:
            return

        if file_type == "pdf":
            if document.pdf_type == TEXT_PDF:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Text-based PDFs do not require OCR.",
                )
            if document.pdf_type != SCANNED_PDF:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PDF must be processed first to detect scan type.",
                )
            return

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type is not supported for OCR. Supported: SCANNED_PDF, PNG, JPG, JPEG.",
        )

    def _extract_text_from_source(self, *, document_id: str, file_path: str) -> str:
        page_images = load_image(file_path)
        page_text_chunks: list[str] = []

        for page_number, page_image in enumerate(page_images, start=1):
            processed_image = preprocess_image(page_image)
            save_processed_image(
                document_id=document_id,
                page_number=page_number,
                image=processed_image,
            )
            page_text = extract_text_with_fallback(processed_image)
            if page_text.strip():
                page_text_chunks.append(f"--- Page {page_number} ---\n{page_text.strip()}")

        extracted_text = "\n\n".join(page_text_chunks)
        if not extracted_text.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="OCR could not extract readable text from the document.",
            )
        return extracted_text

    async def process_document(
        self, db: AsyncSession, *, document_id: UUID, user: User
    ) -> Document:
        document = await self._get_owned_document(db, document_id=document_id, user=user)
        self._validate_ocr_eligible(document)

        if document.ocr_status == OCR_STATUS_COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OCR has already been completed for this document.",
            )

        document = await document_repo.update_ocr_metadata(
            db,
            document=document,
            ocr_status=OCR_STATUS_PROCESSING,
        )

        try:
            extracted_text = self._extract_text_from_source(
                document_id=str(document.id),
                file_path=document.file_path,
            )
            ocr_text_path = save_ocr_text(
                document_id=str(document.id),
                text=extracted_text,
            )

            document = await document_repo.update_ocr_metadata(
                db,
                document=document,
                ocr_status=OCR_STATUS_COMPLETED,
                ocr_text_path=ocr_text_path,
                ocr_processed_at=datetime.now(timezone.utc),
            )
            logger.info("OCR completed for document %s (user %s)", document.id, user.id)
            return document
        except HTTPException:
            await document_repo.update_ocr_metadata(
                db,
                document=document,
                ocr_status=OCR_STATUS_FAILED,
                ocr_processed_at=datetime.now(timezone.utc),
            )
            await db.commit()
            raise
        except Exception as exc:
            await document_repo.update_ocr_metadata(
                db,
                document=document,
                ocr_status=OCR_STATUS_FAILED,
                ocr_processed_at=datetime.now(timezone.utc),
            )
            await db.commit()
            logger.exception("OCR processing failed for document %s", document.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OCR processing failed.",
            ) from exc

    async def get_ocr_result(
        self, db: AsyncSession, *, document_id: UUID, user: User
    ) -> tuple[Document, str]:
        document = await self._get_owned_document(db, document_id=document_id, user=user)

        if document.ocr_status != OCR_STATUS_COMPLETED or not document.ocr_text_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="OCR result not found.",
            )

        ocr_text = load_ocr_text(document.ocr_text_path)
        return document, ocr_text


ocr_service = OCRService()
