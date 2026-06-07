import re
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

# Regular expression to validate strong password rules
# - Min 8 characters
# - At least 1 uppercase letter
# - At least 1 lowercase letter
# - At least 1 number
# - At least 1 special character
PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&._\-+=#^()[\]{}|;':\",./<>?])[A-Za-z\d@$!%*?&._\-+=#^()[\]{}|;':\",./<>?]{8,}$"
)

def validate_strong_password(password: str) -> str:
    if not PASSWORD_REGEX.match(password):
        raise ValueError(
            "Password must be at least 8 characters long, contain at least "
            "one uppercase letter, one lowercase letter, one digit, and one special character."
        )
    return password

class UserCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        return validate_strong_password(v)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_new_password_strength(cls, v: str) -> str:
        return validate_strong_password(v)
