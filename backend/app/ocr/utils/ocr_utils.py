import logging
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

_paddle_ocr_instance: Optional[object] = None


class OCRDependencyError(Exception):
    """Raised when a required OCR engine dependency is unavailable."""


def _get_paddle_ocr():
    global _paddle_ocr_instance
    if _paddle_ocr_instance is None:
        try:
            from paddleocr import PaddleOCR

            _paddle_ocr_instance = PaddleOCR(
                use_angle_cls=True,
                lang=settings.OCR_LANGUAGE,
                show_log=False,
            )
        except ImportError as exc:
            raise OCRDependencyError("PaddleOCR is not installed.") from exc
        except Exception as exc:
            raise OCRDependencyError("PaddleOCR failed to initialize.") from exc
    return _paddle_ocr_instance


def extract_text_paddle(image: np.ndarray) -> str:
    """
    Extracts text from a preprocessed image using PaddleOCR.
    """
    try:
        ocr = _get_paddle_ocr()
        result = ocr.ocr(image, cls=True)
    except OCRDependencyError:
        raise
    except Exception as exc:
        logger.exception("PaddleOCR extraction failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PaddleOCR text extraction failed.",
        ) from exc

    if not result or not result[0]:
        return ""

    lines: list[str] = []
    for line in result[0]:
        if line and len(line) >= 2 and line[1]:
            lines.append(str(line[1][0]).strip())
    return "\n".join(line for line in lines if line)


def extract_text_tesseract(image: np.ndarray) -> str:
    """
    Extracts text from a preprocessed image using Tesseract OCR.
    """
    try:
        import pytesseract
    except ImportError as exc:
        raise OCRDependencyError("pytesseract is not installed.") from exc

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    tesseract_lang = "eng" if settings.OCR_LANGUAGE == "en" else settings.OCR_LANGUAGE

    try:
        text = pytesseract.image_to_string(image, lang=tesseract_lang)
    except OCRDependencyError:
        raise
    except Exception as exc:
        logger.exception("Tesseract extraction failed")
        raise OCRDependencyError("Tesseract OCR is not available.") from exc

    return text.strip()


def extract_text_with_fallback(image: np.ndarray) -> str:
    """
    Runs PaddleOCR first and falls back to Tesseract when needed.
    """
    try:
        text = extract_text_paddle(image)
        if text.strip():
            return text
        logger.info("PaddleOCR returned empty text; falling back to Tesseract.")
    except OCRDependencyError as exc:
        logger.warning("PaddleOCR unavailable: %s", exc)
    except HTTPException:
        logger.warning("PaddleOCR failed; falling back to Tesseract.")

    try:
        return extract_text_tesseract(image)
    except OCRDependencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No OCR engine is available. Install PaddleOCR or Tesseract.",
        ) from exc


def save_ocr_text(*, document_id: str, text: str) -> str:
    """
    Stores OCR output under data/processed/ocr/.
    """
    output_dir = Path(settings.OCR_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"document_{document_id}_ocr.txt"
    output_path.write_text(text, encoding="utf-8")
    return str(output_path)


def load_ocr_text(ocr_text_path: str) -> str:
    path = Path(ocr_text_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OCR text file was not found.",
        )
    return path.read_text(encoding="utf-8")
