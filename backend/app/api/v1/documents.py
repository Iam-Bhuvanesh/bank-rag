import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_active_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.document_service import document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=APIResponse[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Uploads one bank statement file for the authenticated user.
    """
    logger.info("Document upload request received for user %s", current_user.id)
    document = await document_service.upload_document(
        db=db,
        file=file,
        user=current_user,
    )
    return APIResponse.respond_success(
        message="Document uploaded successfully",
        data=DocumentUploadResponse(
            document_id=document.id,
            filename=document.original_filename,
            status=document.status,
        ),
    )


@router.get(
    "",
    response_model=APIResponse[DocumentListResponse],
    status_code=status.HTTP_200_OK,
)
async def list_documents(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists documents owned by the authenticated user.
    """
    documents = await document_service.list_documents(db=db, user=current_user)
    return APIResponse.respond_success(
        message="Documents retrieved successfully",
        data=DocumentListResponse(
            documents=[DocumentResponse.model_validate(doc) for doc in documents]
        ),
    )


@router.get(
    "/{document_id}",
    response_model=APIResponse[DocumentResponse],
    status_code=status.HTTP_200_OK,
)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves metadata for one document owned by the authenticated user.
    """
    document = await document_service.get_document(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    return APIResponse.respond_success(
        message="Document retrieved successfully",
        data=DocumentResponse.model_validate(document),
    )


@router.delete(
    "/{document_id}",
    response_model=APIResponse[None],
    status_code=status.HTTP_200_OK,
)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes one document and its stored file for the authenticated user.
    """
    await document_service.delete_document(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    return APIResponse.respond_success(message="Document deleted successfully")
