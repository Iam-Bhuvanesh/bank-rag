from pathlib import Path
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.utils.jwt_handler import create_access_token, hash_password


@pytest.fixture
async def authenticated_client(db_session: AsyncSession, tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))

    user = User(
        email="documents@bankrag.com",
        full_name="Document Test User",
        password_hash=hash_password("StrongPassword@123"),
        role="USER",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

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
        yield client, user, upload_dir

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_upload_document_api(authenticated_client):
    client, user, upload_dir = authenticated_client

    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", b"%PDF-1.4\nbank statement", "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["filename"] == "statement.pdf"
    assert payload["data"]["status"] == "UPLOADED"
    assert (upload_dir / f"user_{user.id}").exists()


@pytest.mark.anyio
async def test_list_documents_api(authenticated_client):
    client, _, _ = authenticated_client

    await client.post(
        "/api/v1/documents/upload",
        files={"file": ("january.csv", b"date,amount\n2026-01-01,10", "text/csv")},
    )

    response = await client.get("/api/v1/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["data"]["documents"]) == 1
    assert payload["data"]["documents"][0]["original_filename"] == "january.csv"


@pytest.mark.anyio
async def test_delete_document_api(authenticated_client, db_session: AsyncSession):
    client, _, _ = authenticated_client

    upload_response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.xlsx", b"fake workbook", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    document_id = UUID(upload_response.json()["data"]["document_id"])

    document = (
        await db_session.execute(select(Document).where(Document.id == document_id))
    ).scalars().one()
    stored_path = Path(document.file_path)
    assert stored_path.exists()

    response = await client.delete(f"/api/v1/documents/{document_id}")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert not stored_path.exists()

    list_response = await client.get("/api/v1/documents")
    assert list_response.json()["data"]["documents"] == []
