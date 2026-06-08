from uuid import UUID

from pydantic import BaseModel


class OCRProcessResponse(BaseModel):
    """
    Response returned after OCR processing completes.
    """

    document_id: UUID
    ocr_status: str


class OCRResultResponse(BaseModel):
    """
    Response containing OCR status and extracted text.
    """

    document_id: UUID
    ocr_status: str
    ocr_text: str
