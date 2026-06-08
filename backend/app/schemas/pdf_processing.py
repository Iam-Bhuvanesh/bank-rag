from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PDFProcessResponse(BaseModel):
    """
    Response returned after processing a PDF document.
    """

    document_id: UUID
    pdf_type: Optional[str] = None
    status: str


class ProcessedContentResponse(BaseModel):
    """
    Response containing processed text and extracted table rows.
    """

    document_id: UUID
    pdf_type: Optional[str] = None
    status: str
    extracted_text: str
    extracted_tables: list[dict[str, str]]
