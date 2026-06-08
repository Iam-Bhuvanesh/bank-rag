from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class DocumentResponse(BaseModel):
    """
    Detailed document metadata response schema.
    Excludes the internal file_path column for safety.
    """
    id: UUID
    user_id: UUID
    filename: str
    original_filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    status: str
    uploaded_at: datetime
    pdf_type: Optional[str] = None
    processed_at: Optional[datetime] = None
    ocr_status: str = "NOT_REQUIRED"
    ocr_processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class DocumentUploadResponse(BaseModel):
    """
    Simplified response returned immediately after successful file upload.
    """
    document_id: UUID
    filename: str
    status: str

class DocumentListResponse(BaseModel):
    """
    Response schema returning a collection of documents.
    """
    documents: List[DocumentResponse]
