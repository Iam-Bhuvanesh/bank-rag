from pathlib import Path
from unittest.mock import patch

import cv2
import fitz
import httpx
import numpy as np
import pytest
from PIL import Image, ImageDraw
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.ocr.utils.image_utils import preprocess_image
from app.ocr.utils.ocr_utils import save_ocr_text
from app.utils.jwt_handler import create_access_token, hash_password
from app.utils.pdf_utils import SCANNED_PDF


def create_scanned_pdf(path: Path) -> Path:
    image = Image.new("RGB", (500, 200), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 80), "ATM Withdrawal 5000", fill="black")
    image_path = path.with_suffix(".png")
    image.save(image_path)

    document = fitz.open()
    page = document.new_page(width=500, height=200)
    page.insert_image(page.rect, filename=str(image_path))
    document.save(path)
    document.close()
    return path


def test_image_preprocessing():
    image = np.zeros((120, 300, 3), dtype=np.uint8)
    cv2.putText(
        image,
        "Statement",
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
    )

    processed = preprocess_image(image)

    assert processed.ndim == 2
    assert processed.shape[0] == image.shape[0]
    assert processed.shape[1] == image.shape[1]
    assert processed.dtype == np.uint8


def test_ocr_text_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OCR_DIR", str(tmp_path / "ocr"))
    processed = preprocess_image(
        np.full((80, 240, 3), 255, dtype=np.uint8)
    )

    with patch(
        "app.ocr.utils.ocr_utils.extract_text_paddle",
        return_value="ATM Withdrawal\nBalance 25000",
    ):
        from app.ocr.utils.ocr_utils import extract_text_with_fallback

        text = extract_text_with_fallback(processed)

    assert "ATM Withdrawal" in text
    assert "Balance 25000" in text

    saved_path = save_ocr_text(document_id="1", text=text)
    assert Path(saved_path).exists()
    assert "ATM Withdrawal" in Path(saved_path).read_text(encoding="utf-8")


@pytest.fixture
async def ocr_client(db_session: AsyncSession, tmp_path, monkeypatch):
    ocr_dir = tmp_path / "ocr"
    monkeypatch.setattr(settings, "OCR_DIR", str(ocr_dir))

    user = User(
        email="ocr-test@bankrag.com",
        full_name="OCR Test User",
        password_hash=hash_password("StrongPassword@123"),
        role="USER",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    pdf_path = create_scanned_pdf(tmp_path / "scanned_statement.pdf")
    document = Document(
        user_id=user.id,
        filename="scanned_statement.pdf",
        original_filename="scanned_statement.pdf",
        file_type="pdf",
        file_size=pdf_path.stat().st_size,
        file_path=str(pdf_path),
        status="PROCESSED",
        pdf_type=SCANNED_PDF,
        ocr_status="PENDING",
    )
    db_session.add(document)
    await db_session.flush()
    await db_session.refresh(document)

    token = create_access_token(
        data={
            "sub": str(user.id),
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role,
        }
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client, document

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_ocr_endpoint(ocr_client):
    client, document = ocr_client

    with patch(
        "app.ocr.services.ocr_service.extract_text_with_fallback",
        return_value="ATM Withdrawal\nBalance 25000",
    ):
        response = await client.post(f"/api/v1/documents/{document.id}/ocr")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "OCR completed successfully"
    assert payload["data"]["document_id"] == str(document.id)
    assert payload["data"]["ocr_status"] == "COMPLETED"

    result_response = await client.get(f"/api/v1/documents/{document.id}/ocr")
    result_payload = result_response.json()
    assert result_response.status_code == 200
    assert result_payload["data"]["ocr_status"] == "COMPLETED"
    assert "ATM Withdrawal" in result_payload["data"]["ocr_text"]
