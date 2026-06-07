import logging
from datetime import timedelta
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.core.config import settings
from app.models.user import User
from app.repositories.user_repository import user_repo
from app.schemas.auth import UserCreate, TokenResponse, ChangePasswordRequest
from app.services.audit_service import audit_service
from app.utils.jwt_handler import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)

logger = logging.getLogger(__name__)

class AuthService:
    """
    Service layer handling authorization orchestration, token lifecycles, and passwords.
    """
    async def register_user(self, db: AsyncSession, user_in: UserCreate) -> User:
        """
        Registers a new user after validating email uniqueness.
        Hashes password and logs REGISTER audit event.
        """
        # Check duplicate email
        existing_user = await user_repo.get_user_by_email(db, email=user_in.email)
        if existing_user:
            logger.warning(f"Registration failed: Email {user_in.email} already exists.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists."
            )

        # Hash password
        hashed_pw = hash_password(user_in.password)

        # Create user
        db_user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            password_hash=hashed_pw,
            role="USER",  # Standard users default to USER role
            is_active=True,
            is_verified=False
        )
        db.add(db_user)
        await db.flush()
        await db.refresh(db_user)

        # Write audit log
        await audit_service.log_action(
            db=db,
            user_id=db_user.id,
            action="USER_REGISTER",
            resource="users",
            details={"email": db_user.email}
        )

        return db_user

    async def authenticate_user(
        self, db: AsyncSession, email: str, password: str
    ) -> User:
        """
        Validates credentials, updates last_login, and logs USER_LOGIN audit event.
        """
        user = await user_repo.get_user_by_email(db, email=email)
        if not user:
            logger.warning(f"Authentication failed: User with email {email} not found.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password."
            )

        if not user.is_active:
            logger.warning(f"Authentication failed: User account {email} is inactive.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive. Please contact administration."
            )

        # Verify password
        if not verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed: Password mismatch for email {email}.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password."
            )

        # Update login tracking
        await user_repo.update_last_login(db, user_id=user.id)

        # Write audit log
        await audit_service.log_action(
            db=db,
            user_id=user.id,
            action="USER_LOGIN",
            resource="auth",
            details={"email": user.email}
        )

        return user

    def generate_tokens(self, user: User) -> TokenResponse:
        """
        Generates access and refresh tokens for the user.
        """
        # Claims stored inside the access token
        access_token_payload = {
            "sub": str(user.id),
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role
        }
        
        # Claims stored inside the refresh token (minimal to save bandwidth)
        refresh_token_payload = {
            "sub": str(user.id)
        }

        access_token = create_access_token(data=access_token_payload)
        refresh_token = create_refresh_token(data=refresh_token_payload)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    async def refresh_tokens(self, db: AsyncSession, refresh_token: str) -> TokenResponse:
        """
        Exchanges a valid refresh token for a new set of access/refresh tokens.
        """
        try:
            payload = decode_token(refresh_token)
            if payload.get("token_type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type. Refresh token required."
                )
            
            user_id_str = payload.get("sub")
            if not user_id_str:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload."
                )

            # Retrieve user
            user = await user_repo.get_by_id(db, id=user_id_str)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User associated with this token was not found."
                )

            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive."
                )

            # Generate new token pair
            return self.generate_tokens(user)

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired. Please login again."
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token."
            )

    async def change_password(
        self, db: AsyncSession, user: User, password_in: ChangePasswordRequest
    ) -> None:
        """
        Verifies old password, hashes new password, updates database, 
        and logs PASSWORD_CHANGE audit event.
        """
        # Verify old password
        if not verify_password(password_in.old_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password."
            )

        # Prevent setting the same password
        if verify_password(password_in.new_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password cannot be identical to the current password."
            )

        # Hash new password
        hashed_pw = hash_password(password_in.new_password)
        user.password_hash = hashed_pw
        
        db.add(user)
        await db.flush()

        # Write audit log
        await audit_service.log_action(
            db=db,
            user_id=user.id,
            action="USER_PASSWORD_CHANGE",
            resource="users",
            details={"email": user.email}
        )

auth_service = AuthService()
