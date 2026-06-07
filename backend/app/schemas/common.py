from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    """
    Standard Envelope response for all API responses in the application.
    """
    success: bool
    message: str
    data: Optional[T] = None
    errors: Optional[List[Any]] = None

    @classmethod
    def respond_success(cls, message: str = "Success", data: Optional[T] = None) -> "APIResponse[T]":
        return cls(success=True, message=message, data=data)

    @classmethod
    def respond_error(cls, message: str = "Error", errors: Optional[List[Any]] = None) -> "APIResponse[None]":
        return APIResponse[None](success=False, message=message, errors=errors or [])
