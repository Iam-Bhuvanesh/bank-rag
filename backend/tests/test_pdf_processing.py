from pathlib import Path

import fitz
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.utils.jwt_handler import create_access_token, hash_password
from app.utils.pdf_utils import TEXT_PDF, detect_pdf_type, extract_text


def create_sample_pdf(path: Path, text: str = "Bank Statement\nDate Description Debit Credit Balance") -> Path:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path


def test_pdf_type_detection(tmp_path):
    pdf_path = create_sample_pdf(tmp_path / "statement.pdf")

    assert detect_pdf_type(str(pdf_path)) == TEXT_PDF


def test_text_extraction(tmp_path):
    pdf_path = create_sample_pdf(tmp_path / "statement.pdf", "ATM Withdrawal\nBalance 25000")

    text = extract_text(str(pdf_path))

    assert "ATM Withdrawal" in text
    assert "Balance 25000" in text


@pytest.fixture
async def pdf_processing_client(db_session: AsyncSession, tmp_path, monkeypatch):
    processed_dir = tmp_path / "processed"
    monkeypatch.setattr(settings, "PROCESSED_DIR", str(processed_dir))

    user = User(
        email="pdf-processing@bankrag.com",
        full_name="PDF Processing Test User",
        password_hash=hash_password("StrongPassword@123"),
        role="USER",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    pdf_path = create_sample_pdf(tmp_path / "uploaded_statement.pdf")
    document = Document(
        user_id=user.id,
        filename="uploaded_statement.pdf",
        original_filename="uploaded_statement.pdf",
        file_type="pdf",
        file_size=pdf_path.stat().st_size,
        file_path=str(pdf_path),
        status="UPLOADED",
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
async def test_process_endpoint(pdf_processing_client):
    client, document = pdf_processing_client

    response = await client.post(f"/api/v1/documents/{document.id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["document_id"] == str(document.id)
    assert payload["data"]["pdf_type"] == TEXT_PDF
    assert payload["data"]["status"] == "PROCESSED"

    processed_response = await client.get(f"/api/v1/documents/{document.id}/processed")
    processed_payload = processed_response.json()
    assert processed_response.status_code == 200
    assert "Bank Statement" in processed_payload["data"]["extracted_text"]
    assert processed_payload["data"]["extracted_tables"] == []
