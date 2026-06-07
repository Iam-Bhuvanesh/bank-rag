import pytest
from datetime import date
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import UserCreate, ChangePasswordRequest
from app.utils.jwt_handler import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.services.auth_service import auth_service
from app.api.dependencies.auth import RoleChecker

# --- 1. Unit Tests for Cryptography and Tokens ---

def test_password_hashing():
    """Verify that passwords are encrypted securely and match checks."""
    password = "SecurePassword@123"
    hashed = hash_password(password)
    
    assert hashed != password
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")  # bcrypt identifiers
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False

def test_token_creation_and_decoding():
    """Verify JWT Access & Refresh token lifecycles."""
    payload = {"sub": "test_user_id", "email": "test@example.com", "role": "USER"}
    
    access_token = create_access_token(data=payload)
    decoded = decode_token(access_token)
    
    assert decoded["sub"] == "test_user_id"
    assert decoded["email"] == "test@example.com"
    assert decoded["role"] == "USER"
    assert "exp" in decoded

    refresh_token = create_refresh_token(data={"sub": "test_user_id"})
    decoded_refresh = decode_token(refresh_token)
    assert decoded_refresh["sub"] == "test_user_id"
    assert decoded_refresh["token_type"] == "refresh"


# --- 2. Service Layer Integration Tests ---

@pytest.mark.anyio
async def test_user_registration_service(db_session: AsyncSession):
    """Test user registration flow including hashing and audit logging."""
    user_in = UserCreate(
        email="register_test@bankrag.com",
        full_name="Register Test User",
        password="StrongPassword@123"
    )
    
    # Register user
    db_user = await auth_service.register_user(db=db_session, user_in=user_in)
    assert db_user.id is not None
    assert db_user.email == "register_test@bankrag.com"
    assert db_user.role == "USER"
    assert verify_password("StrongPassword@123", db_user.password_hash) is True

    # Test duplicate email check
    with pytest.raises(HTTPException) as exc:
        await auth_service.register_user(db=db_session, user_in=user_in)
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in exc.value.detail

@pytest.mark.anyio
async def test_user_login_authentication(db_session: AsyncSession):
    """Test login authentication validation and token issuance."""
    email = "auth_test@bankrag.com"
    password = "StrongPassword@123"
    
    # 1. Create a user manually
    hashed_pw = hash_password(password)
    user = User(
        email=email,
        full_name="Auth User",
        password_hash=hashed_pw,
        role="USER",
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()
    
    # 2. Test login with correct password
    authenticated_user = await auth_service.authenticate_user(
        db=db_session, email=email, password=password
    )
    assert authenticated_user.id == user.id
    
    # 3. Verify login updates last_login
    assert authenticated_user.last_login is not None

    # 4. Test login with incorrect password
    with pytest.raises(HTTPException) as exc:
        await auth_service.authenticate_user(
            db=db_session, email=email, password="wrongpassword"
        )
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

    # 5. Test login with inactive user
    user.is_active = False
    db_session.add(user)
    await db_session.flush()
    with pytest.raises(HTTPException) as exc:
        await auth_service.authenticate_user(
            db=db_session, email=email, password=password
        )
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.anyio
async def test_token_refresh_exchange(db_session: AsyncSession):
    """Test token refresh logic."""
    email = "refresh_test@bankrag.com"
    user = User(
        email=email,
        password_hash=hash_password("StrongPassword@123"),
        role="USER",
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    tokens = auth_service.generate_tokens(user)
    
    # Validate refresh token can generate new access token
    new_tokens = await auth_service.refresh_tokens(db=db_session, refresh_token=tokens.refresh_token)
    assert new_tokens.access_token is not None
    assert new_tokens.refresh_token is not None


@pytest.mark.anyio
async def test_password_change_flow(db_session: AsyncSession):
    """Test password update flow validation."""
    user = User(
        email="pwchange@bankrag.com",
        password_hash=hash_password("CurrentPassword@123"),
        role="USER",
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    # Change password
    pw_in = ChangePasswordRequest(
        old_password="CurrentPassword@123",
        new_password="NewStrongPassword@456"
    )
    await auth_service.change_password(db=db_session, user=user, password_in=pw_in)
    
    # Verify new password works
    assert verify_password("NewStrongPassword@456", user.password_hash) is True


# --- 3. Role-Based Access Control (RBAC) Tests ---

def test_rbac_role_checker():
    """Verify that RoleChecker validates user roles correctly."""
    admin_checker = RoleChecker(allowed_roles=["ADMIN"])
    user_checker = RoleChecker(allowed_roles=["USER", "ADMIN"])

    admin_user = User(role="ADMIN", is_active=True)
    normal_user = User(role="USER", is_active=True)
    auditor_user = User(role="AUDITOR", is_active=True)

    # Admin Checker
    assert admin_checker(admin_user) == admin_user
    with pytest.raises(HTTPException) as exc:
        admin_checker(normal_user)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    with pytest.raises(HTTPException) as exc:
        admin_checker(auditor_user)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    # User & Admin Checker
    assert user_checker(admin_user) == admin_user
    assert user_checker(normal_user) == normal_user
    with pytest.raises(HTTPException) as exc:
        user_checker(auditor_user)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
