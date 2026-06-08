import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_active_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.pdf_processing import PDFProcessResponse, ProcessedContentResponse
from app.services.pdf_service import pdf_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["PDF Processing"])


@router.post(
    "/{document_id}/process",
    response_model=APIResponse[PDFProcessResponse],
    status_code=status.HTTP_200_OK,
)
async def process_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Processes an authenticated user's uploaded PDF document.
    """
    logger.info("PDF processing request received for document %s", document_id)
    document, _, _ = await pdf_service.process_document(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    return APIResponse.respond_success(
        message="Document processed successfully",
        data=PDFProcessResponse(
            document_id=document.id,
            pdf_type=document.pdf_type,
            status=document.status,
        ),
    )


@router.get(
    "/{document_id}/processed",
    response_model=APIResponse[ProcessedContentResponse],
    status_code=status.HTTP_200_OK,
)
async def get_processed_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns extracted text and table rows for a processed PDF.
    """
    document, text, tables = await pdf_service.get_processed_content(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    return APIResponse.respond_success(
        message="Processed content retrieved successfully",
        data=ProcessedContentResponse(
            document_id=document.id,
            pdf_type=document.pdf_type,
            status=document.status,
            extracted_text=text,
            extracted_tables=tables,
        ),
    )
