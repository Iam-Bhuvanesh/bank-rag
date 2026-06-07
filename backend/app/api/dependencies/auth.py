import logging
from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.core.config import settings
from app.database.session import get_db
from app.models.user import User
from app.repositories.user_repository import user_repo
from app.utils.jwt_handler import decode_token

logger = logging.getLogger(__name__)

# Configures the standard OAuth2 Password flow token extractor.
# Points to the login endpoint.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

async def get_current_user(
    db: AsyncSession = Depends(get_db), 
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Validates the JWT access token and retrieves the current authenticated user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode and validate token signature & expiration
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise credentials_exception

    user = await user_repo.get_by_id(db, id=user_id_str)
    if user is None:
        raise credentials_exception
        
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Validates that the current user is active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Inactive user account."
        )
    return current_user

class RoleChecker:
    """
    Reusable Role-Based Access Control (RBAC) dependency checker.
    Example usage: Depends(RoleChecker(["ADMIN", "AUDITOR"]))
    """
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(
        self, 
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if current_user.role not in self.allowed_roles:
            logger.warning(
                f"RBAC Denied | User: {current_user.id} (Role: {current_user.role}) "
                f"attempted to access resource requiring: {self.allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action."
            )
        return current_user

# Pre-defined aliases for dependency injection
require_admin = RoleChecker(["ADMIN"])
require_user_or_admin = RoleChecker(["USER", "ADMIN"])
