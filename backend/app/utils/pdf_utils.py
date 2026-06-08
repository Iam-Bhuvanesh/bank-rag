import json
import logging
from pathlib import Path
from typing import Any

import fitz
import pdfplumber
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

TEXT_PDF = "TEXT_PDF"
SCANNED_PDF = "SCANNED_PDF"


def _validate_pdf_path(file_path: str) -> Path:
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source PDF file was not found.",
        )
    if path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document is not a PDF file.",
        )
    return path


def _tables_path_for(text_path: Path) -> Path:
    return text_path.with_suffix(".tables.json")


def detect_pdf_type(file_path: str) -> str:
    """
    Detects whether a PDF contains selectable text.
    Returns TEXT_PDF for text-based PDFs, otherwise SCANNED_PDF.
    """
    path = _validate_pdf_path(file_path)
    try:
        with fitz.open(path) as document:
            for page in document:
                if page.get_text("text").strip():
                    return TEXT_PDF
    except Exception as exc:
        logger.exception("Failed to detect PDF type for %s", path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted PDF file.",
        ) from exc

    return SCANNED_PDF


def extract_text(file_path: str) -> str:
    """
    Extracts selectable text from a PDF.
    """
    path = _validate_pdf_path(file_path)
    try:
        text_chunks: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_chunks.append(f"--- Page {page_number} ---\n{page_text.strip()}")
        return "\n\n".join(text_chunks)
    except Exception as exc:
        logger.exception("Failed to extract text from %s", path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to extract text from PDF.",
        ) from exc


def _normalize_table_row(headers: list[str], row: list[Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for index, header in enumerate(headers):
        key = (header or f"column_{index + 1}").strip().lower().replace(" ", "_")
        value = row[index] if index < len(row) else ""
        normalized[key] = "" if value is None else str(value).strip()
    return normalized


def extract_tables(file_path: str) -> list[dict[str, str]]:
    """
    Extracts simple tabular data from PDF pages using pdfplumber.
    """
    path = _validate_pdf_path(file_path)
    extracted_rows: list[dict[str, str]] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    clean_rows = [
                        ["" if cell is None else str(cell).strip() for cell in row]
                        for row in table
                        if row and any(cell for cell in row)
                    ]
                    if not clean_rows:
                        continue

                    headers = clean_rows[0]
                    for row in clean_rows[1:]:
                        extracted_rows.append(_normalize_table_row(headers, row))
    except Exception as exc:
        logger.exception("Failed to extract tables from %s", path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to extract tables from PDF.",
        ) from exc

    return extracted_rows


def save_processed_text(
    *,
    document_id: str,
    text: str,
    tables: list[dict[str, str]],
) -> str:
    """
    Stores extracted text and extracted table JSON under the processed directory.
    """
    processed_dir = Path(settings.PROCESSED_DIR).resolve()
    processed_dir.mkdir(parents=True, exist_ok=True)

    text_path = processed_dir / f"document_{document_id}.txt"
    tables_path = _tables_path_for(text_path)

    text_path.write_text(text, encoding="utf-8")
    tables_path.write_text(json.dumps(tables, indent=2), encoding="utf-8")

    return str(text_path)


def load_processed_text(text_path: str) -> str:
    path = Path(text_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processed text file was not found.",
        )
    return path.read_text(encoding="utf-8")


def load_processed_tables(text_path: str) -> list[dict[str, str]]:
    path = _tables_path_for(Path(text_path))
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
