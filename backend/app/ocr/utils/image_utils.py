import logging
from pathlib import Path
from typing import Iterator

import cv2
import fitz
import numpy as np
from fastapi import HTTPException, status
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _validate_source_path(file_path: str) -> Path:
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source file was not found.",
        )
    return path


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _load_image_file(path: Path) -> np.ndarray:
    suffix = path.suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image format: {suffix}",
        )
    try:
        with Image.open(path) as image:
            return _pil_to_bgr(image)
    except Exception as exc:
        logger.exception("Failed to load image %s", path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file.",
        ) from exc


def _load_pdf_pages(path: Path) -> Iterator[np.ndarray]:
    try:
        with fitz.open(path) as document:
            if document.page_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PDF contains no pages.",
                )
            for page in document:
                pixmap = page.get_pixmap(dpi=settings.OCR_DPI, alpha=False)
                channels = pixmap.n
                array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, channels
                )
                if channels == 1:
                    yield cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
                else:
                    yield cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to render PDF pages for OCR: %s", path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to read PDF for OCR processing.",
        ) from exc


def load_image(file_path: str) -> list[np.ndarray]:
    """
    Loads one or more page images from a supported source file.
    Returns a list so scanned PDFs can be processed page by page.
    """
    path = _validate_source_path(file_path)
    suffix = path.suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        return [_load_image_file(path)]
    if suffix == ".pdf":
        return list(_load_pdf_pages(path))

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="File type is not supported for OCR.",
    )


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """
    Applies grayscale conversion, denoising, enhancement, and thresholding.
    """
    if image is None or image.size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image cannot be preprocessed.",
        )

    try:
        gray = (
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image.copy()
        )

        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        thresholded = cv2.adaptiveThreshold(
            enhanced,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )
        return thresholded
    except Exception as exc:
        logger.exception("Image preprocessing failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image preprocessing failed.",
        ) from exc


def save_processed_image(
    *,
    document_id: str,
    page_number: int,
    image: np.ndarray,
) -> str:
    """
    Persists a preprocessed page image for debugging and audit trails.
    """
    output_dir = Path(settings.OCR_DIR).resolve() / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"document_{document_id}_page_{page_number}.png"
    cv2.imwrite(str(output_path), image)
    return str(output_path)
