import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_active_user
from app.database.session import get_db
from app.models.user import User
from app.ocr.services.ocr_service import ocr_service
from app.schemas.common import APIResponse
from app.schemas.ocr import OCRProcessResponse, OCRResultResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["OCR"])


@router.post(
    "/{document_id}/ocr",
    response_model=APIResponse[OCRProcessResponse],
    status_code=status.HTTP_200_OK,
)
async def process_document_ocr(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Runs OCR on a scanned PDF or image document owned by the authenticated user.
    """
    logger.info("OCR request received for document %s", document_id)
    document = await ocr_service.process_document(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    return APIResponse.respond_success(
        message="OCR completed successfully",
        data=OCRProcessResponse(
            document_id=document.id,
            ocr_status=document.ocr_status,
        ),
    )


@router.get(
    "/{document_id}/ocr",
    response_model=APIResponse[OCRResultResponse],
    status_code=status.HTTP_200_OK,
)
async def get_document_ocr(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns OCR status and extracted text for a processed document.
    """
    document, ocr_text = await ocr_service.get_ocr_result(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    return APIResponse.respond_success(
        message="OCR result retrieved successfully",
        data=OCRResultResponse(
            document_id=document.id,
            ocr_status=document.ocr_status,
            ocr_text=ocr_text,
        ),
    )
