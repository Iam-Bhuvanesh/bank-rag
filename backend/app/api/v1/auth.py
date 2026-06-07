import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.api.dependencies.auth import get_current_active_user
from app.schemas.common import APIResponse
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest
)
from app.services.auth_service import auth_service
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/register", 
    response_model=APIResponse[UserResponse], 
    status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserCreate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a new user account with strong password requirements.
    Logs audit trail event.
    """
    logger.info(f"Registering new user: {user_in.email}")
    db_user = await auth_service.register_user(db=db, user_in=user_in)
    user_res = UserResponse.model_validate(db_user)
    return APIResponse.respond_success(
        message="User registered successfully",
        data=user_res
    )

@router.post(
    "/login", 
    response_model=APIResponse[TokenResponse], 
    status_code=status.HTTP_200_OK
)
async def login(
    credentials: UserLogin, 
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticates user credentials and issues Access and Refresh tokens.
    Logs audit trail event.
    """
    logger.info(f"User login attempt: {credentials.email}")
    user = await auth_service.authenticate_user(
        db=db, 
        email=credentials.email, 
        password=credentials.password
    )
    tokens = auth_service.generate_tokens(user)
    return APIResponse.respond_success(
        message="Login successful",
        data=tokens
    )

@router.post(
    "/refresh", 
    response_model=APIResponse[TokenResponse], 
    status_code=status.HTTP_200_OK
)
async def refresh(
    refresh_in: RefreshTokenRequest, 
    db: AsyncSession = Depends(get_db)
):
    """
    Rotates access and refresh tokens using a valid refresh token.
    """
    logger.info("Token refresh request received.")
    new_tokens = await auth_service.refresh_tokens(db=db, refresh_token=refresh_in.refresh_token)
    return APIResponse.respond_success(
        message="Tokens refreshed successfully",
        data=new_tokens
    )

@router.post(
    "/logout", 
    response_model=APIResponse[None], 
    status_code=status.HTTP_200_OK
)
async def logout(
    current_user: User = Depends(get_current_active_user), 
    db: AsyncSession = Depends(get_db)
):
    """
    Logs out the user and logs a USER_LOGOUT audit trail event.
    """
    logger.info(f"Logging out user: {current_user.email}")
    await audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action="USER_LOGOUT",
        resource="auth",
        details={"email": current_user.email}
    )
    return APIResponse.respond_success(
        message="Logout successful. Please discard active tokens."
    )

@router.get(
    "/me", 
    response_model=APIResponse[UserResponse], 
    status_code=status.HTTP_200_OK
)
async def get_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    Fetches the profile of the current authenticated user.
    """
    logger.info(f"Retrieving active user profile for: {current_user.email}")
    user_res = UserResponse.model_validate(current_user)
    return APIResponse.respond_success(
        message="Profile retrieved successfully",
        data=user_res
    )

@router.post(
    "/change-password", 
    response_model=APIResponse[None], 
    status_code=status.HTTP_200_OK
)
async def change_password(
    password_in: ChangePasswordRequest, 
    current_user: User = Depends(get_current_active_user), 
    db: AsyncSession = Depends(get_db)
):
    """
    Changes the password for the current logged-in user.
    Verifies old password, validates strength of new password, and logs USER_PASSWORD_CHANGE audit event.
    """
    logger.info(f"Password update request for: {current_user.email}")
    await auth_service.change_password(
        db=db, 
        user=current_user, 
        password_in=password_in
    )
    return APIResponse.respond_success(
        message="Password updated successfully."
    )
