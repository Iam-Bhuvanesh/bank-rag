import pytest
from datetime import date
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.document import Document
from app.models.transaction import Transaction
from app.models.chat import ChatHistory
from app.models.audit import AuditLog
from app.repositories.base import BaseRepository

# Rename schemas to avoid Pytest trying to collect them as Test suites
class UserCreateTestSchema(BaseModel):
    email: str
    full_name: str
    password_hash: str
    is_active: bool = True

class UserUpdateTestSchema(BaseModel):
    full_name: str

class DocumentCreateTestSchema(BaseModel):
    user_id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int

# Initialize repositories
user_repo = BaseRepository[User, UserCreateTestSchema, UserUpdateTestSchema](User)

@pytest.mark.anyio
async def test_db_connection(db_session: AsyncSession):
    """Verify that we can successfully execute queries on the database session."""
    result = await db_session.execute(select(1))
    assert result.scalar() == 1

@pytest.mark.anyio
async def test_user_repository_crud(db_session: AsyncSession):
    """Test standard Create, Read, Update, Delete using BaseRepository."""
    # 1. Create User
    user_in = UserCreateTestSchema(
        email="test_repo@bankrag.com",
        full_name="Repository Test User",
        password_hash="hashed_pw_123"
    )
    db_user = await user_repo.create(db_session, obj_in=user_in)
    assert db_user.id is not None
    assert db_user.email == "test_repo@bankrag.com"
    assert db_user.full_name == "Repository Test User"
    
    # 2. Get User By ID
    retrieved_user = await user_repo.get_by_id(db_session, db_user.id)
    assert retrieved_user is not None
    assert retrieved_user.email == "test_repo@bankrag.com"

    # 3. Update User
    update_in = UserUpdateTestSchema(full_name="Updated Repo Name")
    updated_user = await user_repo.update(db_session, db_obj=db_user, obj_in=update_in)
    assert updated_user.full_name == "Updated Repo Name"

    # 4. Get All Users
    all_users = await user_repo.get_all(db_session)
    assert len(all_users) >= 1
    assert any(u.id == db_user.id for u in all_users)

    # 5. Delete User
    deleted_user = await user_repo.delete(db_session, id=db_user.id)
    assert deleted_user.id == db_user.id
    
    # Verify deletion
    post_delete_user = await user_repo.get_by_id(db_session, db_user.id)
    assert post_delete_user is None

@pytest.mark.anyio
async def test_model_relationships(db_session: AsyncSession):
    """Verify model mappings and relationship integrity (cascade delete)."""
    # 1. Create a user
    user = User(
        email="test_relations@bankrag.com",
        full_name="Relational Test User",
        password_hash="password123"
    )
    db_session.add(user)
    await db_session.flush()

    # 2. Upload a document for this user
    doc = Document(
        user_id=user.id,
        filename="bank_statement_2026.pdf",
        original_filename="statement.pdf",
        file_type="application/pdf",
        file_size=1024,
        processing_status="completed"
    )
    db_session.add(doc)
    await db_session.flush()

    # 3. Parse a transaction inside the document
    tx = Transaction(
        document_id=doc.id,
        transaction_date=date(2026, 6, 7),
        description="Coffee shop payment",
        debit_amount=4.50,
        merchant_name="Starbucks",
        transaction_type="debit"
    )
    db_session.add(tx)
    await db_session.flush()

    # 4. Log chat query related to the document
    chat = ChatHistory(
        user_id=user.id,
        question="How much did I spend at Starbucks?",
        answer="You spent $4.50 at Starbucks."
    )
    db_session.add(chat)
    await db_session.flush()

    # 5. Perform Audit logging
    audit = AuditLog(
        user_id=user.id,
        action="QUERY_TRANSACTION",
        resource="chat_history",
        details={"question_length": len(chat.question)}
    )
    db_session.add(audit)
    await db_session.flush()

    # 6. Eagerly load user relationships to test integrity
    query = (
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.documents).selectinload(Document.transactions),
            selectinload(User.chat_history),
            selectinload(User.audit_logs)
        )
    )
    res = await db_session.execute(query)
    user_loaded = res.scalars().one()
    
    assert len(user_loaded.documents) == 1
    assert len(user_loaded.documents[0].transactions) == 1
    assert len(user_loaded.chat_history) == 1
    assert len(user_loaded.audit_logs) == 1
    assert user_loaded.documents[0].transactions[0].merchant_name == "Starbucks"

    # 7. Test Cascade Delete
    await db_session.delete(user_loaded)
    await db_session.flush()

    # Check that document and transaction are deleted cascade-style
    stmt_doc = select(Document).where(Document.id == doc.id)
    stmt_tx = select(Transaction).where(Transaction.id == tx.id)
    stmt_chat = select(ChatHistory).where(ChatHistory.id == chat.id)
    
    res_doc = await db_session.execute(stmt_doc)
    res_tx = await db_session.execute(stmt_tx)
    res_chat = await db_session.execute(stmt_chat)

    assert res_doc.scalars().first() is None
    assert res_tx.scalars().first() is None
    assert res_chat.scalars().first() is None
