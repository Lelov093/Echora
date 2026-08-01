"""Common Pydantic schemas: envelope, pagination, errors."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


# ── API Envelope ─────────────────────────────────────────────────────

class ApiMeta(BaseModel):
    """Metadata container for API responses."""
    request_id: str | None = None
    elapsed_ms: int | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int = 1
    page_size: int = 20
    total: int = 0
    total_pages: int = 0


class ApiError(BaseModel):
    """Unified API error."""
    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiResponse(BaseModel, Generic[T]):
    """Unified API response envelope.

    All REST responses use this shape:
        {"data": ..., "error": null, "meta": ...}
    """
    data: T | None = None
    error: ApiError | None = None
    meta: ApiMeta | PaginationMeta | dict[str, Any] | None = None


# ── Paginated List ───────────────────────────────────────────────────

class PaginatedList(BaseModel, Generic[T]):
    """Paginated item list with PaginationMeta."""
    items: list[T] = Field(default_factory=list)
    pagination: PaginationMeta = Field(default_factory=PaginationMeta)


# ── Helper factories ─────────────────────────────────────────────────

def ok(data: T | None = None, meta: dict[str, Any] | None = None) -> dict:
    """Build a success API response dict."""
    result: dict[str, Any] = {"data": data, "error": None, "meta": meta or {}}
    return result


def paginated_ok(items: list[T], page: int, page_size: int, total: int) -> dict:
    """Build a paginated success API response dict."""
    import math
    return {
        "data": {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": max(1, math.ceil(total / max(1, page_size))),
            },
        },
        "error": None,
        "meta": {},
    }


def err(code: str, message: str, details: dict[str, Any] | None = None) -> dict:
    """Build an error API response dict."""
    return {
        "data": None,
        "error": {"code": code, "message": message, "details": details},
        "meta": None,
    }


# ── Query Params ─────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    """Standard pagination query parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: str | None = None
    order: str | None = Field(default="desc", pattern="^(asc|desc)$")
