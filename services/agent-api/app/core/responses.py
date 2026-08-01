"""Unified API response envelope."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiMeta(BaseModel):
    """Metadata container for API responses."""
    timestamp: str | None = None
    page: int | None = None
    page_size: int | None = None
    total: int | None = None


class ApiError(BaseModel):
    """Unified API error object."""
    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiResponse(BaseModel, Generic[T]):
    """Unified API response envelope.

    All REST API responses MUST use this structure:
        {"data": ..., "error": null, "meta": {...}}
    """
    data: T | None = None
    error: ApiError | None = None
    meta: ApiMeta | None = None


def ok(data: T | None = None, meta: ApiMeta | None = None) -> ApiResponse[T]:
    """Factory for successful API responses."""
    return ApiResponse[T](data=data, error=None, meta=meta or ApiMeta())


def err(code: str, message: str, details: dict[str, Any] | None = None) -> ApiResponse[None]:
    """Factory for error API responses."""
    return ApiResponse[None](
        data=None,
        error=ApiError(code=code, message=message, details=details),
        meta=None,
    )
